# apps/core/streams/preview.py

from typing import Optional

from django.conf import settings

from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key


def _cdn_url(key: str | None) -> str | None:
    """
    Build clean CDN URL.
    """

    if not key:
        return None

    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")
    if not base:
        return None

    return f"{base}/{str(key).lstrip('/')}"


def _safe_preview_key(obj, field_name: str) -> Optional[str]:
    """
    Resolve preview key safely.

    Used for normal FileField/ImageField media such as:
    - image
    - thumbnail
    """

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

    try:
        key = resolve_fallback_filefield_key(obj, field_name)
        if key:
            return key
    except Exception:
        pass

    return None


def _is_moment_like(obj) -> bool:
    """
    Detect Moment-like object without importing Moment here.
    """

    return (
        hasattr(obj, "image_items")
        or hasattr(obj, "cover_image_id")
        or hasattr(obj, "cover_image_key")
    )


def _ordered_image_items(obj) -> list[dict]:
    """
    Return valid ordered JSON-backed image items.
    """

    try:
        if hasattr(obj, "normalized_image_items"):
            items = obj.normalized_image_items()
        else:
            items = getattr(obj, "image_items", None) or []

        if not isinstance(items, list):
            return []

        cleaned = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("id")
            and item.get("key")
        ]

        return sorted(
            cleaned,
            key=lambda item: int(item.get("order", 0) or 0),
        )

    except Exception:
        return []


def _cover_image_key(obj) -> str | None:
    """
    Resolve pinned/primary Moment photo key.
    """

    try:
        if hasattr(obj, "cover_image_key"):
            key = obj.cover_image_key()
            if key:
                return str(key).lstrip("/")

        items = _ordered_image_items(obj)
        if not items:
            return None

        cover_id = str(getattr(obj, "cover_image_id", "") or "")

        if cover_id:
            for item in items:
                if str(item.get("id")) == cover_id:
                    key = str(item.get("key") or "").lstrip("/")
                    return key or None

        key = str(items[0].get("key") or "").lstrip("/")
        return key or None

    except Exception:
        return None


def _image_items_payload(obj) -> list[dict]:
    """
    Build lightweight image item metadata for Stream clients.

    Important:
    - field_name is used by asset-delivery resolving/warmup.
    - cdn_url/image_url are used by web/iOS as direct safe preview sources.
    """

    items = _ordered_image_items(obj)
    cover_id = str(getattr(obj, "cover_image_id", "") or "")

    payload = []

    for index, item in enumerate(items):
        item_id = str(item.get("id") or "").strip()
        key = str(item.get("key") or "").strip().lstrip("/")

        if not item_id or not key:
            continue

        url = _cdn_url(key)

        payload.append(
            {
                "id": item_id,
                "key": key,
                "order": int(item.get("order", index) or index),
                "file_name": item.get("file_name") or key.split("/")[-1],
                "mime_type": item.get("mime_type") or "",
                "size": int(item.get("size") or 0),
                "is_cover": item_id == cover_id or bool(item.get("is_cover")),
                "field_name": f"image_items:{item_id}",

                # Critical for web stream carousel.
                "cdn_url": url,
                "image_url": url,
            }
        )

    return payload


def _cover_image_payload(obj, image_items: list[dict]) -> dict | None:
    """
    Build cover descriptor for Stream clients.
    """

    if not image_items:
        if getattr(obj, "image", None):
            key = _safe_preview_key(obj, "image")

            return {
                "id": None,
                "field_name": "image",
                "source": "image",
                "cdn_url": _cdn_url(key),
                "image_url": _cdn_url(key),
            }

        return None

    cover_id = str(getattr(obj, "cover_image_id", "") or "")

    if cover_id:
        for item in image_items:
            if str(item.get("id")) == cover_id:
                return {
                    "id": item["id"],
                    "field_name": item["field_name"],
                    "source": "image_items",
                    "cdn_url": item.get("cdn_url"),
                    "image_url": item.get("image_url"),
                }

    first = image_items[0]

    return {
        "id": first["id"],
        "field_name": first["field_name"],
        "source": "image_items",
        "cdn_url": first.get("cdn_url"),
        "image_url": first.get("image_url"),
    }


def _attach_moment_photo_metadata(out: dict, obj) -> dict:
    """
    Attach multi-photo Moment metadata to preview payload.
    """

    image_items = _image_items_payload(obj)
    cover_image = _cover_image_payload(obj, image_items)

    out["image_items"] = image_items
    out["cover_image_id"] = getattr(obj, "cover_image_id", None)
    out["cover_image"] = cover_image

    return out


def build_stream_preview(obj, *, subtype: str) -> dict:
    """
    Build frontend-safe preview payload.
    """

    out = {
        "thumbnail_url": None,
        "image_url": None,
        "poster_url": None,
        "type": None,
        "has_video": False,

        # Multi-photo Moment fields.
        "image_items": [],
        "cover_image_id": None,
        "cover_image": None,
    }

    # Testimony-like object.
    if hasattr(obj, "type"):
        out["type"] = getattr(obj, "type", None)

        if subtype == "written":
            return out

        thumb_key = _safe_preview_key(obj, "thumbnail")
        image_key = _safe_preview_key(obj, "image")

        thumbnail_url = _cdn_url(thumb_key)
        image_url = _cdn_url(image_key)

        out["thumbnail_url"] = thumbnail_url
        out["image_url"] = image_url
        out["poster_url"] = thumbnail_url or image_url

        return out

    # Video object.
    if subtype == "video":
        thumb_key = _safe_preview_key(obj, "thumbnail")
        image_key = _safe_preview_key(obj, "image")

        thumbnail_url = _cdn_url(thumb_key)
        image_url = _cdn_url(image_key)

        out["type"] = "video"
        out["has_video"] = True
        out["thumbnail_url"] = thumbnail_url
        out["image_url"] = image_url
        out["poster_url"] = thumbnail_url or image_url

        return out

    # Image object.
    if subtype == "image":
        if _is_moment_like(obj):
            cover_key = _cover_image_key(obj)
            image_key = cover_key or _safe_preview_key(obj, "image")
            thumb_key = None
        else:
            image_key = _safe_preview_key(obj, "image")
            thumb_key = _safe_preview_key(obj, "thumbnail")

        image_url = _cdn_url(image_key)
        thumbnail_url = _cdn_url(thumb_key)

        out["type"] = "image"
        out["image_url"] = image_url
        out["thumbnail_url"] = thumbnail_url
        out["poster_url"] = image_url or thumbnail_url

        if _is_moment_like(obj):
            out = _attach_moment_photo_metadata(out, obj)

            # Keep cover URL aligned with selected cover item if available.
            cover_image = out.get("cover_image") or {}
            cover_url = cover_image.get("cdn_url") or cover_image.get("image_url")

            if cover_url:
                out["image_url"] = cover_url
                out["poster_url"] = cover_url

        return out

    return out