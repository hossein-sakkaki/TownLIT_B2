# apps/accounts/services/veriff_security.py

import hmac
import hashlib
from django.conf import settings

def verify_veriff_signature(raw_body: bytes, received_signature: str) -> bool:
    """
    Verify Veriff webhook signature using HMAC-SHA256
    """
    if not received_signature:
        return False

    secret = settings.VERIFF_WEBHOOK_SECRET.encode("utf-8")
    expected_signature = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()

    # Constant-time compare to avoid timing attacks
    return hmac.compare_digest(expected_signature, received_signature)
