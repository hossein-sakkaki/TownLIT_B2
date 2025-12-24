# apps/conversation/utils.py
from django.http import HttpRequest


# get_websocket_url -------------------------------------------------------------------------
def get_websocket_url(request: HttpRequest, dialogue_slug: str) -> str:
    scheme = "wss" if request.is_secure() else "ws"
    host = request.get_host()
    return f"{scheme}://{host}/ws/conversation/{dialogue_slug}/"


# get_message_content -----------------------------------------------------------------------
def get_message_content(message, user):
    if message.is_system:
        return message.system_event or "[System message]"

    if message.is_encrypted:
        try:
            return message.decrypt_message(user.private_key)
        except Exception:
            return "[Failed to decrypt message]"

    return message.content_encrypted.decode() if message.content_encrypted else "[Empty]"




