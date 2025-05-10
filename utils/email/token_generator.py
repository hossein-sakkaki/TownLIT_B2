from django.core import signing
from django.conf import settings

UNSUBSCRIBE_SALT = "unsubscribe-token"

def generate_unsubscribe_token(user_id: int) -> str:
    return signing.dumps(user_id, salt=UNSUBSCRIBE_SALT)

def decode_unsubscribe_token(token: str) -> int:
    return signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * 7)  # 7 روز اعتبار
