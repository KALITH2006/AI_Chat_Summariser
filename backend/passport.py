import base64
import json
from datetime import datetime

def generate_passport(session_data: dict) -> str:
    """Encodes session data to Base64 passport."""
    if "createdAt" not in session_data:
        session_data["createdAt"] = datetime.utcnow().isoformat()
    json_data = json.dumps(session_data)
    passport_bytes = base64.b64encode(json_data.encode("utf-8"))
    return passport_bytes.decode("utf-8")

def decode_passport(passport_str: str) -> dict:
    """Decodes Base64 passport string to dictionary."""
    try:
        decoded_bytes = base64.b64decode(passport_str)
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid passport format: {e}")
