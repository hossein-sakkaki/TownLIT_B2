# apps/organizations/modules/church/services/pastoral_crypto.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError


def _cipher():
    return Fernet(settings.FERNET_KEY)


def encrypt_pastoral_text(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return _cipher().encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_pastoral_text(value: str | None) -> str:
    token = (value or "").strip()
    if not token:
        return ""
    try:
        return _cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValidationError("Pastoral care encrypted content could not be decrypted.") from exc
