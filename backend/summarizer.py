import os
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
from keybert import KeyBERT
from huggingface_hub import login
from utils import chunk_transcript

# Login to Hugging Face
hf_token = os.getenv("HF_TOKEN")
if hf_token:
    login(token=hf_token)

print("Initializing Advanced Conversational NLP Pipeline... (This loads models ONCE)")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Hardware detection: {device.upper()}")

# Global models (Singleton pattern)
summariser_model = None
summariser_tokenizer = None
emotion_analyzer = None
kw_model = None
models_loaded = False

try:
    # Summarization Model: SAMSum tuned
    # Using AutoModel directly because pipeline("summarization") was removed in Transformers v5
    model_name = "philschmid/bart-large-cnn-samsum"
    summariser_tokenizer = AutoTokenizer.from_pretrained(model_name)
    summariser_model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)

    # Emotion Model: go_emotions (28 emotions)
    emotion_analyzer = pipeline(
        "text-classification",
        model="SamLowe/roberta-base-go_emotions",
        device=0 if device == "cuda" else -1,
        top_k=3,
        model_kwargs={"low_cpu_mem_usage": True}
    )

    # Embeddings / Keywords / Topics: bge-small-en-v1.5
    kw_model = KeyBERT("BAAI/bge-small-en-v1.5")
    
    models_loaded = True
    print("Models successfully loaded into memory!")
except Exception as e:
    print(f"Model initialization failed: {e}")
    models_loaded = False

def _run_summariser(text: str, max_length: int, min_length: int) -> str:
    inputs = summariser_tokenizer(text, max_length=1024, truncation=True, return_tensors="pt").to(device)
    summary_ids = summariser_model.generate(
        inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        max_length=max_length,
        min_length=min_length,
        num_beams=4,
        length_penalty=2.0,
        early_stopping=True,
        do_sample=False,
    )
    return summariser_tokenizer.decode(summary_ids[0], skip_special_tokens=True)

def chunk_transcript(transcript: str, max_tokens: int = 800) -> list[str]:
    """Tokenizer-aware rough chunking to preserve dialogue boundaries."""
    lines = transcript.split("\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for line in lines:
        line_length = len(line.split())
        if current_length + line_length > max_tokens:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = line_length
        else:
            current_chunk.append(line)
            current_length += line_length

    if current_chunk:
        chunks.append("\n".join(current_chunk))
    
    return chunks

def process_transcript(transcript: str, method: str, detail_level: str, tone: str):
    if not models_loaded:
        raise RuntimeError("Models are not loaded.")

    with torch.no_grad():
        # 1. Chunking
        chunks = chunk_transcript(transcript, max_tokens=800)

        # 2. Hierarchical Summarization
        chunk_summaries = []
        for chunk in chunks:
            if not chunk.strip():
                continue
            max_len = min(200, len(chunk.split()))
            min_len = min(50, max_len // 2) if max_len > 100 else 10
            if max_len < 20:
                chunk_summaries.append(chunk)
                continue
            
            summary_text = _run_summariser(chunk, max_length=max_len, min_length=min_len)
            chunk_summaries.append(summary_text)

        combined_summary = "\n".join(chunk_summaries)

        # 3. Master Summary
        if len(chunks) > 1:
            max_len = min(400, len(combined_summary.split()))
            min_len = min(100, max_len // 2) if max_len > 100 else 30
            if max_len >= 30:
                final_summary = _run_summariser(combined_summary, max_length=max_len, min_length=min_len)
            else:
                final_summary = combined_summary
        else:
            final_summary = combined_summary

        # Apply formatting
        if detail_level == "Bullet Points":
            sentences = final_summary.replace("? ", "?\n").replace("! ", "!\n").replace(". ", ".\n").split("\n")
            final_summary = "\n".join([f"• {s.strip()}" for s in sentences if s.strip()])

        # 4. Emotion Extraction
        try:
            emotion_res = emotion_analyzer(transcript[:2000], truncation=True)[0]
            emotions = [
                {"label": em["label"].title(), "score": round(em["score"], 4)}
                for em in emotion_res
            ]
            dominant_emotion = emotions[0]["label"]
            confidence = emotions[0]["score"]
        except Exception as e:
            emotions = [{"label": "Neutral", "score": 1.0}]
            dominant_emotion = "Neutral"
            confidence = 1.0
            print(f"Emotion error: {e}")

        emotion_data = {
            "dominant_emotion": dominant_emotion,
            "confidence": confidence,
            "top_emotions": emotions
        }

        # 5. Keyword & Topic Extraction
        try:
            keywords_raw = kw_model.extract_keywords(transcript, keyphrase_ngram_range=(1, 2), stop_words='english', top_n=6)
            keywords = [kw[0].title() for kw in keywords_raw]
            topics = [kw for kw in keywords if " " in kw][:3]
            if not topics:
                topics = keywords[:2]
        except Exception as e:
            keywords = []
            topics = ["General Chat"]
            print(f"Keyword error: {e}")

        # 6. Resume Prompt & Next Steps
        next_steps = [
            f"Review key technical decisions around: {', '.join(keywords[:3]) if keywords else 'the main topic'}.",
            "Verify the flow and accuracy of the conversational summary.",
            "Continue building the next integration phase."
        ]
        
        resume_prompt = (
            f"We were building a solution involving {topics[0] if topics else 'this topic'} "
            f"using {', '.join(keywords[:3]) if keywords else 'these concepts'}. "
            "Please continue from where we left off based on the established context."
        )

        return {
            "summary": final_summary,
            "topics": topics,
            "keywords": keywords,
            "emotions": emotion_data,
            "nextSteps": next_steps,
            "resumePrompt": resume_prompt
        }
