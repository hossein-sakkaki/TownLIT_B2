# apps/conversation/utils.py

import base64
from django.http import HttpRequest


# get_websocket_url -------------------------------------------------------------------------
def get_websocket_url(request: HttpRequest) -> str:
    scheme = "wss" if request.is_secure() else "ws"
    host = request.get_host()
    return f"{scheme}://{host}/ws"


# get_message_content -----------------------------------------------------------------------
def get_message_content(message, user=None):
    """
    Return readable plaintext only for server-safe cases.

    Rules:
    - System messages: return stored readable text if possible.
    - Encrypted private messages: do NOT decrypt on server here.
    - Plain/group-style messages: decode stored base64 payload safely.
    """
    raw = message.content_encrypted

    # Empty safeguard
    if not raw:
        return "[Empty]"

    # Normalize bytes
    if isinstance(raw, memoryview):
        raw = raw.tobytes()

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")

    # System message: prefer stored text
    if message.is_system:
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            return decoded or "[System message]"
        except Exception:
            return message.system_event or "[System message]"

    # Private encrypted message should not be decrypted here
    has_encryptions = getattr(message, "encryptions", None)
    try:
        if has_encryptions is not None and message.encryptions.exists():
            return "[Encrypted message]"
    except Exception:
        pass

    # Plain/group-style stored message
    try:
        return base64.b64decode(raw).decode("utf-8")
    except Exception:
        return "[Unreadable message]"