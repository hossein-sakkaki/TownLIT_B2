# apps/asset_delivery/services/playback_resolver.py

from typing import Optional


def resolve_fallback_filefield_key(target_obj, field_name: str) -> Optional[str]:
    """
    Fallback when job output_path is missing.
    Tries to read FileField.name (S3 key).
    """
    try:
        f = getattr(target_obj, field_name, None)
        key = getattr(f, "name", None)
        return (key or "").strip() or None
    except Exception:
        return None
