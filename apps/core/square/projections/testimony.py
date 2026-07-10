# apps/core/square/projections/testimony.py

from .base import SquareProjection
from .registry import register_projection
from .media import (
    safe_preview_key,
    cdn_url,
    media_asset,
    media_dimensions,
    variants_payload,
    video_preview_payload,
    video_qualities_payload,
)


def _asset_key(asset: dict | None) -> str | None:
    if not isinstance(asset, dict):
        return None

    key = asset.get("key")

    if not key:
        return None

    cleaned = str(key).strip().lstrip("/")
    return cleaned or None


def _asset_url(asset: dict | None) -> str | None:
    key = _asset_key(asset)
    return cdn_url(key)


def _has_asset_key(asset: dict | None) -> bool:
    return bool(_asset_key(asset))


def _image_preview_payload(
    *,
    obj,
    field_name: str,
    fallback_field_name: str | None = None,
) -> dict:
    """
    Build a preferred image preview payload.

    Used for audio testimony artwork:
    - preferred field: audio_artwork
    - fallback field: thumbnail
    """

    preferred_asset = media_asset(obj, field_name)
    fallback_asset = (
        media_asset(obj, fallback_field_name)
        if fallback_field_name
        else {}
    )

    preferred_key = (
        _asset_key(preferred_asset)
        or safe_preview_key(obj, field_name)
    )

    fallback_key = (
        _asset_key(fallback_asset)
        or (
            safe_preview_key(obj, fallback_field_name)
            if fallback_field_name
            else None
        )
    )

    preferred_url = cdn_url(preferred_key)
    fallback_url = cdn_url(fallback_key)

    if preferred_key:
        selected_asset = preferred_asset
        selected_url = preferred_url
    else:
        selected_asset = fallback_asset
        selected_url = fallback_url

    dimensions = media_dimensions(selected_asset)

    return {
        "preferred_key": preferred_key,
        "fallback_key": fallback_key,
        "preferred_url": preferred_url,
        "fallback_url": fallback_url,
        "selected_asset": selected_asset,
        "selected_url": selected_url,
        "width": dimensions.get("width"),
        "height": dimensions.get("height"),
        "aspect_ratio": dimensions.get("aspect_ratio"),
        "variants": variants_payload(
            selected_asset.get("variants")
            if isinstance(selected_asset, dict)
            else None
        ),
    }


@register_projection("testimony")
class TestimonySquareProjection(SquareProjection):

    def get_preview(self):
        obj = self.obj
        content_type = getattr(obj, "type", "written")

        if content_type == "video":
            return self._video_preview()

        if content_type == "audio":
            return self._audio_preview()

        return self._written_preview()

    # -------------------------------------------------
    # Preview types
    # -------------------------------------------------

    def _video_preview(self):
        obj = self.obj

        thumb_key = safe_preview_key(obj, "thumbnail")
        thumbnail_url = cdn_url(thumb_key)

        thumbnail_asset = media_asset(obj, "thumbnail")
        video_asset = media_asset(obj, "video")

        video_dimensions = media_dimensions(video_asset)
        thumbnail_dimensions = media_dimensions(thumbnail_asset)

        dimensions = (
            video_dimensions
            if video_dimensions.get("aspect_ratio")
            else thumbnail_dimensions
        )

        return {
            "thumbnail_url": thumbnail_url,
            "image_url": None,
            "poster_url": thumbnail_url,
            "has_video": True,
            "type": "video",

            # Layout must follow the video, not the thumbnail.
            "width": dimensions.get("width"),
            "height": dimensions.get("height"),
            "aspect_ratio": dimensions.get("aspect_ratio"),
            "duration_ms": video_asset.get("duration_ms"),

            # Thumbnail stays as static fallback/poster.
            "variants": variants_payload(thumbnail_asset.get("variants")),

            # Moving preview is preferred by Square UI when available.
            "preview_video": video_preview_payload(obj, "video"),
            "video_qualities": video_qualities_payload(obj, "video"),
        }

    def _audio_preview(self):
        obj = self.obj

        artwork = _image_preview_payload(
            obj=obj,
            field_name="audio_artwork",
            fallback_field_name="thumbnail",
        )

        return {
            # Keep thumbnail_url as legacy/static fallback only.
            "thumbnail_url": artwork.get("fallback_url"),

            # image_url/poster_url should prefer audio_artwork.
            "image_url": artwork.get("selected_url"),
            "poster_url": artwork.get("selected_url") or artwork.get("fallback_url"),

            "has_video": False,
            "type": "audio",

            "width": artwork.get("width"),
            "height": artwork.get("height"),
            "aspect_ratio": artwork.get("aspect_ratio"),
            "duration_ms": None,

            "variants": artwork.get("variants") or {},
            "preview_video": None,
            "video_qualities": [],
        }

    def _written_preview(self):
        return {
            "thumbnail_url": None,
            "image_url": None,
            "poster_url": None,
            "has_video": False,
            "type": "written",

            "width": None,
            "height": None,
            "aspect_ratio": None,
            "duration_ms": None,

            "variants": {},
            "preview_video": None,
            "video_qualities": [],
        }

    def get_meta(self):
        return {
            "title": (getattr(self.obj, "title", "") or "")[:120],
            "excerpt": (getattr(self.obj, "content", "") or "")[:160],
        }