def chunk_transcript(transcript: str, max_words: int = 500) -> list[str]:
    """Splits a large transcript into chunks of words."""
    words = transcript.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
    return chunks

def get_word_count(text: str) -> int:
    return len(text.split())

def get_turn_count(text: str) -> int:
    # Count non-empty lines as turns
    lines = [line for line in text.split("\n") if line.strip()]
    return len(lines)
