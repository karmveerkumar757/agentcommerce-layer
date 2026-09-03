def extract_intent(message: str) -> dict:
    """Extracts intent from raw message. In a production app, this would use an LLM call."""
    return {
        "raw": message,
        "likely_intent": "chat"
    }
