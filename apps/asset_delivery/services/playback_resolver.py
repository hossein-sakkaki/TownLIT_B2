# apps/asset_delivery/services/playback_resolver.py

from typing import Optional


MOMENT_IMAGE_ITEMS_PREFIX = "image_items"


def _clean_key(value) -> Optional[str]:
    """
    Normalize a storage key.
    """
    key = str(value or "").strip().lstrip("/")
    return key or None


def _normalized_image_items(target_obj) -> list[dict]:
    """
    Read JSON-backed Moment image items safely.
    """
    try:
        if hasattr(target_obj, "normalized_image_items"):
            return target_obj.normalized_image_items()

        items = getattr(target_obj, "image_items", None)
        if not isinstance(items, list):
            return []

        return [
            item for item in items
            if isinstance(item, dict) and item.get("key")
        ]
    except Exception:
        return []


def _resolve_moment_cover_key(target_obj) -> Optional[str]:
    """
    Resolve pinned cover image for photo Moments.
    """
    try:
        if hasattr(target_obj, "cover_image_key"):
            return _clean_key(target_obj.cover_image_key())

        items = _normalized_image_items(target_obj)
        if not items:
            return None

        cover_id = str(getattr(target_obj, "cover_image_id", "") or "")

        if cover_id:
            for item in items:
                if str(item.get("id")) == cover_id:
                    return _clean_key(item.get("key"))

        return _clean_key(items[0].get("key"))
    except Exception:
        return None


def _resolve_moment_image_item_key(
    target_obj,
    selector: str,
) -> Optional[str]:
    """
    Resolve image_items:<id> or image_items:<index>.
    """
    selector = str(selector or "").strip()
    if not selector:
        return None

    items = _normalized_image_items(target_obj)
    if not items:
        return None

    # Resolve by stable image item id.
    for item in items:
        if str(item.get("id")) == selector:
            return _clean_key(item.get("key"))

    # Resolve by numeric index as a fallback.
    if selector.isdigit():
        index = int(selector)
        ordered = sorted(
            items,
            key=lambda item: int(item.get("order", 0) or 0),
        )

        if 0 <= index < len(ordered):
            return _clean_key(ordered[index].get("key"))

    return None


def _resolve_moment_json_image_key(
    target_obj,
    field_name: str,
) -> Optional[str]:
    """
    Resolve JSON-backed Moment image fields.
    """
    field_name = str(field_name or "").strip()

    if not field_name:
        return None

    # cover_image always means the pinned/primary photo.
    if field_name in {"cover_image", "cover", "pinned_image"}:
        return _resolve_moment_cover_key(target_obj)

    # image_items:<id> or image_items:<index>
    prefix = f"{MOMENT_IMAGE_ITEMS_PREFIX}:"
    if field_name.startswith(prefix):
        selector = field_name[len(prefix):]
        return _resolve_moment_image_item_key(
            target_obj=target_obj,
            selector=selector,
        )

    return None


def resolve_fallback_filefield_key(
    target_obj,
    field_name: str,
) -> Optional[str]:
    """
    Fallback when job output_path is missing.

    Supports:
    - normal FileField/ImageField fields
    - Moment JSON-backed photo fields:
      cover_image
      image_items:<id>
      image_items:<index>
    """
    field_name = str(field_name or "").strip()

    if not field_name:
        return None

    # JSON-backed Moment photos.
    json_key = _resolve_moment_json_image_key(
        target_obj=target_obj,
        field_name=field_name,
    )
    if json_key:
        return json_key

    # Legacy FileField/ImageField fallback.
    try:
        f = getattr(target_obj, field_name, None)
        key = getattr(f, "name", None)
        return _clean_key(key)
    except Exception:
        return None