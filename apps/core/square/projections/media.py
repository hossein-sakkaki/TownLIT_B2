# apps/core/square/projections/media.py

from django.conf import settings
from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key


def safe_preview_key(obj, field_name: str):
    """
    Safe preview resolver for feed usage.
    NEVER raises exception.
    NEVER requires conversion.
    """

    # Try converted media first
    try:
        key = get_latest_done_output_path(
            target_obj=obj,
            field_name=field_name,
            kind="image",
        )
        if key:
            return key
    except Exception:
        pass

    # Fallback to original file
    try:
        key = resolve_fallback_filefield_key(obj, field_name)
        if key:
            return key
    except Exception:
        pass

    return None


def cdn_url(key: str | None) -> str | None:
    if not key:
        return None
    return f"{settings.ASSET_CDN_BASE_URL.rstrip('/')}/{key.lstrip('/')}"
