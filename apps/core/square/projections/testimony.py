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


@register_projection("testimony")
class TestimonySquareProjection(SquareProjection):

    def get_preview(self):
        obj = self.obj
        content_type = getattr(obj, "type", "written")

        thumb_key = safe_preview_key(obj, "thumbnail")
        image_key = safe_preview_key(obj, "image")

        thumbnail_url = cdn_url(thumb_key)
        image_url = cdn_url(image_key)

        thumbnail_asset = media_asset(obj, "thumbnail")
        video_asset = media_asset(obj, "video")

        dimensions = media_dimensions(thumbnail_asset)

        if content_type == "video":
            video_dimensions = media_dimensions(video_asset)
            if video_dimensions.get("aspect_ratio"):
                dimensions = video_dimensions

        return {
            "thumbnail_url": thumbnail_url,
            "image_url": image_url,
            "poster_url": thumbnail_url or image_url,
            "has_video": content_type == "video",
            "type": content_type,

            "width": dimensions.get("width"),
            "height": dimensions.get("height"),
            "aspect_ratio": dimensions.get("aspect_ratio"),
            "duration_ms": video_asset.get("duration_ms") if content_type == "video" else None,

            "variants": variants_payload(thumbnail_asset.get("variants")),
            "preview_video": video_preview_payload(obj, "video") if content_type == "video" else None,
            "video_qualities": video_qualities_payload(obj, "video") if content_type == "video" else [],
        }

    def get_meta(self):
        return {
            "title": (getattr(self.obj, "title", "") or "")[:120],
            "excerpt": (getattr(self.obj, "content", "") or "")[:160],
        }