from __future__ import annotations

from django.conf import settings
from django.db.models.fields.files import FieldFile


DEFAULT_AVATAR_PATH = "/static/defaults/default-avatar.png"
DEFAULT_AVATAR_FILENAME = "default-avatar.png"


def _normalize_site_url(url: str) -> str:
    u = (url or "").strip()
    return u[:-1] if u.endswith("/") else u


SITE_URL = _normalize_site_url(getattr(settings, "SITE_URL", "https://www.townlit.com"))
DEFAULT_AVATAR_URL = f"{SITE_URL}{DEFAULT_AVATAR_PATH}"


def _avatar_value_to_str(value) -> str:
    """
    Normalize avatar value to a comparable string.

    Handles:
    - None
    - empty string
    - ImageFieldFile / FieldFile
    - relative paths
    - absolute URLs
    """
    if not value:
        return ""

    # ImageFieldFile / FieldFile
    if isinstance(value, FieldFile):
        # If file not set
        if not value.name:
            return ""
        return value.url or value.name or ""

    # Anything else -> string
    return str(value).strip()


def is_default_avatar_value(value) -> bool:
    """
    Return True if the stored avatar points to the default avatar.
    """
    v = _avatar_value_to_str(value)
    if not v:
        return True

    # 1) exact canonical match
    if v == DEFAULT_AVATAR_URL:
        return True

    # 2) contains default path (any host / CDN)
    if DEFAULT_AVATAR_PATH in v:
        return True

    # 3) filename match (signed URLs, resized paths)
    if v.split("?", 1)[0].endswith(DEFAULT_AVATAR_FILENAME):
        return True

    return False
