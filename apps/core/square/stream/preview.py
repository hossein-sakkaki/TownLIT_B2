# apps/core/square/stream/preview.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from apps.asset_delivery.services.job_resolver import get_latest_done_output_path
from apps.asset_delivery.services.playback_resolver import resolve_fallback_filefield_key


def _join_cdn_url(key: str) -> str:
    """Build clean CDN URL (NO signed query)."""
    base = (getattr(settings, "ASSET_CDN_BASE_URL", "") or "").rstrip("/")
    k = (key or "").lstrip("/")
    if not base:
        raise ValueError("ASSET_CDN_BASE_URL is not set.")
    return f"{base}/{k}"


def _pick_key_for_image_kind(target_obj, field_name: str) -> Optional[str]:
    """
    Best-effort key resolver for image/thumbnail previews.
    - Tries latest conversion output_path first
    - Falls back to filefield storage key
    """
    # Note: for both 'image' and 'thumbnail' we treat job kind as "image"
    key = get_latest_done_output_path(
        target_obj=target_obj,
        field_name=field_name,
        kind="image",
    )
    if not key:
        key = resolve_fallback_filefield_key(target_obj, field_name)
    return key or None


def build_stream_preview(obj, *, subtype: str) -> dict:
    """
    Return preview block expected by frontend.

    Important:
    - Returns CLEAN CDN URLs (no signed query)
    - Private access is enforced by CloudFront signed cookies (frontend warmup)
    """
    # Default payload
    out = {
        "thumbnail_url": None,
        "image_url": None,
        "type": None,        # for testimony (video|audio|written)
        "has_video": False,  # for moment (boolean)
    }

    # ---------------------------------------------
    # Testimony (has .type)
    # ---------------------------------------------
    if hasattr(obj, "type"):
        # normalize
        out["type"] = getattr(obj, "type", None)

        # Written testimony => no media preview
        if subtype == "written":
            return out

        # Video/Audio: prefer thumbnail if exists, else image
        # (Adjust field names if your Testimony model uses different ones)
        thumb_key = _pick_key_for_image_kind(obj, "thumbnail")
        img_key = _pick_key_for_image_kind(obj, "image")

        if thumb_key:
            out["thumbnail_url"] = _join_cdn_url(thumb_key)
        if img_key:
            out["image_url"] = _join_cdn_url(img_key)

        return out

    # ---------------------------------------------
    # Moment (image/video fields)
    # ---------------------------------------------
    # Video moment => thumbnail is primary
    if subtype == "video":
        out["has_video"] = True

        thumb_key = _pick_key_for_image_kind(obj, "thumbnail")
        if thumb_key:
            out["thumbnail_url"] = _join_cdn_url(thumb_key)

        # Optional fallback: some systems also generate an "image" poster
        img_key = _pick_key_for_image_kind(obj, "image")
        if img_key:
            out["image_url"] = _join_cdn_url(img_key)

        return out

    # Image moment => image primary, thumbnail fallback
    if subtype == "image":
        img_key = _pick_key_for_image_kind(obj, "image")
        if img_key:
            out["image_url"] = _join_cdn_url(img_key)

        thumb_key = _pick_key_for_image_kind(obj, "thumbnail")
        if thumb_key:
            out["thumbnail_url"] = _join_cdn_url(thumb_key)

        return out

    return out
