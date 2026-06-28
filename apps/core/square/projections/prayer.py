# apps/core/square/projections/prayer.py

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


@register_projection("pray")
class PrayerSquareProjection(SquareProjection):
    """
    Lightweight Square projection for Prayer.
    """

    def get_preview(self):
        obj = self.obj

        thumb_key = safe_preview_key(obj, "thumbnail")
        image_key = safe_preview_key(obj, "image")

        thumbnail_url = cdn_url(thumb_key)
        image_url = cdn_url(image_key)

        has_video = bool(getattr(obj, "video", None))

        image_asset = media_asset(obj, "image")
        thumbnail_asset = media_asset(obj, "thumbnail")
        video_asset = media_asset(obj, "video")

        if has_video:
            dimensions = media_dimensions(video_asset)
            if not dimensions.get("aspect_ratio"):
                dimensions = media_dimensions(thumbnail_asset)
            if not dimensions.get("aspect_ratio"):
                dimensions = media_dimensions(image_asset)
        else:
            dimensions = media_dimensions(image_asset)

        return {
            "thumbnail_url": thumbnail_url,
            "image_url": image_url,
            "poster_url": thumbnail_url or image_url,
            "has_video": has_video,
            "type": "video" if has_video else "image",
            "status": getattr(obj, "status", None),

            "width": dimensions.get("width"),
            "height": dimensions.get("height"),
            "aspect_ratio": dimensions.get("aspect_ratio"),
            "duration_ms": video_asset.get("duration_ms") if has_video else None,

            "variants": variants_payload(
                thumbnail_asset.get("variants") if has_video else image_asset.get("variants")
            ),
            "preview_video": video_preview_payload(obj, "video") if has_video else None,
            "video_qualities": video_qualities_payload(obj, "video") if has_video else [],
        }

    def get_meta(self):
        return {
            "excerpt": (getattr(self.obj, "caption", "") or "")[:160],
            "is_completed": getattr(self.obj, "status", "") in ("answered", "not_answered"),
        }