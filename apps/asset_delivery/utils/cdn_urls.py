# apps/asset_delivery/utils/cdn_urls.py
from __future__ import annotations

from urllib.parse import urlparse
from django.conf import settings


def _strip_query(url: str) -> str:
    # Keep path only (drop ?Policy=... etc.)
    return url.split("?", 1)[0]


def normalize_storage_key(value: str | None) -> str | None:
    """
    Normalize an ImageField value into a storage key (path in bucket).
    Supports:
    - "accounts/photos/..jpg" (key)
    - "https://bucket.s3.../accounts/photos/..jpg" (full S3 url)
    - "/accounts/photos/..jpg" (leading slash)
    - Signed urls (we drop query)
    """
    if not value:
        return None

    v = value.strip()
    if not v:
        return None

    v = _strip_query(v)

    # Full URL?
    if v.startswith("http://") or v.startswith("https://"):
        u = urlparse(v)
        path = (u.path or "").lstrip("/")
        return path or None

    # Leading slash path
    if v.startswith("/"):
        return v.lstrip("/") or None

    # Already a key
    return v


def build_cdn_url(value: str | None, *, base_url: str | None = None) -> str | None:
    """
    Build clean CDN URL from either a key or a full URL.
    Returns None if base_url missing.
    """
    key = normalize_storage_key(value)
    if not key:
        return None

    base = (base_url or getattr(settings, "ASSET_CDN_BASE_URL", "") or "").strip()
    if not base:
        return None

    return f"{base.rstrip('/')}/{key.lstrip('/')}"
