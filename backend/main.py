import json
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, get_db_connection
from summarizer import process_transcript
from utils import get_word_count, get_turn_count
from passport import generate_passport, decode_passport

app = FastAPI(title="AI Chat Summariser API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

class SummariseRequest(BaseModel):
    transcript: str
    method: str
    length: str
    tone: str

class PassportDecodeRequest(BaseModel):
    passport: str

@app.post("/summarise")
def summarise_chat(req: SummariseRequest):
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")

    word_count = get_word_count(req.transcript)
    turn_count = get_turn_count(req.transcript)

    try:
        result = process_transcript(req.transcript, req.method, req.length, req.tone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    summary_words = get_word_count(result["summary"])
    compression_ratio = f"{(summary_words / word_count) * 100:.1f}%" if word_count > 0 else "0%"

    session_data = {
        "summary": result["summary"],
        "topics": result["topics"],
        "keywords": result["keywords"],
        "emotions": result["emotions"],
        "nextSteps": result["nextSteps"],
        "resumePrompt": result["resumePrompt"],
    }
    passport_str = generate_passport(session_data)
    
    session_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (id, summary, topics, keywords, emotions, passport) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, result["summary"], json.dumps(result["topics"]), json.dumps(result["keywords"]), json.dumps(result["emotions"]), passport_str)
        )
        conn.commit()

    return {
        "id": session_id,
        "summary": result["summary"],
        "topics": result["topics"],
        "keywords": result["keywords"],
        "emotions": result["emotions"],
        "nextSteps": result["nextSteps"],
        "resumePrompt": result["resumePrompt"],
        "wordCount": word_count,
        "turnCount": turn_count,
        "compressionRatio": compression_ratio,
        "passport": passport_str
    }

@app.post("/passport/decode")
def api_decode_passport(req: PassportDecodeRequest):
    try:
        data = decode_passport(req.passport)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/history")
def get_history():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
    history = []
    for row in rows:
        history.append({
            "id": row["id"],
            "summary": row["summary"],
            "topics": json.loads(row["topics"]) if row["topics"] else [],
            "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
            "emotions": json.loads(row["emotions"]) if row["emotions"] else {},
            "passport": row["passport"],
            "created_at": row["created_at"]
        })
    return {"history": history}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
