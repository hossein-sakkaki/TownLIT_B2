# apps/core/square/projections/media.py

from __future__ import annotations

from django.conf import settings

from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key


def clean_key(value) -> str | None:
    if not value:
        return None

    raw = getattr(value, "name", value)

    if not raw:
        return None

    cleaned = str(raw).strip().lstrip("/")
    return cleaned or None


def cdn_url(key: str | None) -> str | None:
    key = clean_key(key)

    if not key:
        return None

    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")

    if not base:
        return None

    return f"{base}/{key}"


def media_asset(obj, field_name: str) -> dict:
    assets = getattr(obj, "media_assets", None) or {}

    if not isinstance(assets, dict):
        return {}

    value = assets.get(field_name)
    return value if isinstance(value, dict) else {}


def media_dimensions(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {
            "width": None,
            "height": None,
            "aspect_ratio": None,
        }

    return {
        "width": payload.get("width"),
        "height": payload.get("height"),
        "aspect_ratio": payload.get("aspect_ratio"),
    }


def variants_payload(variants: dict | None) -> dict:
    if not isinstance(variants, dict):
        return {}

    output = {}

    for name, payload in variants.items():
        if not isinstance(payload, dict):
            continue

        key = clean_key(payload.get("key"))
        url = cdn_url(key)

        output[name] = {
            **payload,
            "key": key,
            "cdn_url": url,
            "image_url": url,
            "url": url,
        }

    return output


def image_asset_payload(obj, field_name: str) -> dict:
    asset = media_asset(obj, field_name)
    key = clean_key(asset.get("key")) or safe_preview_key(obj, field_name)
    url = cdn_url(key)

    return {
        **asset,
        "key": key,
        "cdn_url": url,
        "image_url": url,
        "url": url,
        "variants": variants_payload(asset.get("variants")),
        **media_dimensions(asset),
    }


def video_preview_payload(obj, field_name: str = "video") -> dict | None:
    asset = media_asset(obj, field_name)
    preview = asset.get("preview")

    if not isinstance(preview, dict):
        return None

    key = clean_key(preview.get("key"))
    url = cdn_url(key)

    if not url:
        return None

    return {
        **preview,
        "key": key,
        "cdn_url": url,
        "video_url": url,
        "url": url,
    }


def video_qualities_payload(obj, field_name: str = "video") -> list:
    asset = media_asset(obj, field_name)
    qualities = asset.get("qualities")

    return qualities if isinstance(qualities, list) else []


def safe_preview_key(obj, field_name: str):
    """
    Safe preview resolver for feed usage.
    NEVER raises exception.
    NEVER requires conversion.
    """

    asset_key = clean_key(media_asset(obj, field_name).get("key"))

    if asset_key:
        return asset_key

    try:
        key = get_latest_done_output_path(
            target_obj=obj,
            field_name=field_name,
            kind="image",
        )
        if key:
            return clean_key(key)
    except Exception:
        pass

    try:
        key = resolve_fallback_filefield_key(obj, field_name)
        if key:
            return clean_key(key)
    except Exception:
        pass

    return None