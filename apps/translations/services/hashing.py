# apps/translations/services/hashing.py
import hashlib


def hash_text(text: str) -> str:
    """Return SHA256 hash of source text."""
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
