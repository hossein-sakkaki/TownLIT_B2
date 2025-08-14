# common/aws/s3_utils.py
from __future__ import annotations

import logging
from typing import Optional

from botocore.exceptions import ClientError
from django.conf import settings

from .aws_clients import s3_client  # shared, centralized boto3 client

logger = logging.getLogger(__name__)

# ---------------- Category detection helpers ----------------

# Tune these prefixes to match your avatar/cover-like assets that re-render often.
AVATAR_LIKE_PREFIXES = (
    "accounts/photos/custom_user/",
    "accounts/photos/groups/",
    "conversation/cover/",
    "dialogue/cover/",
    "main/image/official_thumbnails/",
)

def is_avatar_like(key: str) -> bool:
    if not key:
        return False
    k = key.lstrip("/")
    return any(k.startswith(p) for p in AVATAR_LIKE_PREFIXES)

def is_hls_asset(key: str) -> bool:
    if not key:
        return False
    k = key.lower()
    return k.endswith(".m3u8") or k.endswith(".ts") or "/hls/" in k


# ---------------- Low-level helpers ----------------

def get_file_size(key: str) -> int:
    """Return object size in bytes (raises on error)."""
    resp = s3_client.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
    )
    return resp["ContentLength"]


def _choose_expiry_seconds(
    key: str,
    size_bytes: Optional[int],
    requested: Optional[int],
) -> int:
    """
    Decide final expiry:
    - explicit `requested` (if provided) takes precedence
    - avatar-like -> 1800s (30 min)
    - HLS -> 900s (15 min)
    - else -> dynamic by size ~= 6 sec/MB, clamped to [300, 3600]
    - fallback -> 600s
    """
    if isinstance(requested, int) and requested > 0:
        return requested

    if is_avatar_like(key):
        return 1800  # 30 minutes

    if is_hls_asset(key):
        return 900  # 15 minutes

    if isinstance(size_bytes, int) and size_bytes > 0:
        approx = int((size_bytes / (1024 * 1024)) * 6)  # ~6 sec per MB
        return max(300, min(approx, 3600))

    return 600  # safe default


# ---------------- Public API ----------------

def generate_presigned_url(
    key: str,
    expires_in: Optional[int] = None,
    force_download: bool = False,
) -> Optional[str]:
    """
    Create a GET pre-signed URL using the shared s3_client.
    - Smart expiry per key category (avatars/hls/others)
    - Optionally force download via Content-Disposition
    - Adds ResponseCacheControl for avatar-like assets to reduce churn
    """
    if not key:
        return None

    # Try to fetch file size for dynamic expiry; non-fatal on error
    size_bytes: Optional[int] = None
    try:
        size_bytes = get_file_size(key)
    except Exception as e:
        logger.warning(f"Could not head_object for {key}: {e}")

    # Decide final expiry
    final_expiry = _choose_expiry_seconds(key, size_bytes, expires_in)

    params = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": key,
    }

    if force_download:
        filename = key.split("/")[-1]
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    # For avatar-like assets, hint caches to keep it around for the expiry window
    if is_avatar_like(key):
        cache_secs = min(final_expiry, 3600)  # cap at 1 hour
        params["ResponseCacheControl"] = f"public, max-age={cache_secs}"

    try:
        # Using the shared client keeps configuration consistent across the app
        return s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=final_expiry,
        )
    except ClientError as e:
        logger.error(f"Error generating signed URL for {key}: {e}")
        return None


def get_file_url(
    key: str,
    default_url: Optional[str] = None,
    expires_in: Optional[int] = None,
    force_download: bool = False,
) -> Optional[str]:
    """
    Resolve final URL for a stored object:
    - If key is already a full URL -> return as-is
    - If SERVE_FILES_PUBLICLY -> return public URL (MEDIA_URL + key)
    - Else -> return pre-signed URL with smart expiry
    """
    if not key:
        return default_url

    # Already a full URL?
    if key.startswith("http://") or key.startswith("https://"):
        return key

    # Public serving mode (e.g., via CDN/public bucket)
    if getattr(settings, "SERVE_FILES_PUBLICLY", False):
        return f"{settings.MEDIA_URL}{key}"

    # Private mode -> presigned
    try:
        url = generate_presigned_url(key, expires_in=expires_in, force_download=force_download)
        return url or default_url
    except Exception as e:
        logger.error(f"get_file_url fallback due to error for key={key}: {e}")
        return default_url
