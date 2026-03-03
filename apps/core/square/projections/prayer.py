# apps/core/square/projections/prayer.py

from .base import SquareProjection
from .registry import register_projection
from .media import safe_preview_key, cdn_url


@register_projection("pray")
class PrayerSquareProjection(SquareProjection):
    """
    Lightweight Square projection for Prayer.
    """

    def get_preview(self):
        obj = self.obj

        # Prefer thumbnail for video
        thumb_key = safe_preview_key(obj, "thumbnail")
        image_key = safe_preview_key(obj, "image")

        return {
            "thumbnail_url": cdn_url(thumb_key),
            "image_url": cdn_url(image_key),
            "has_video": bool(getattr(obj, "video", None)),
            "status": getattr(obj, "status", None),  # waiting / answered / not_answered
        }

    def get_meta(self):
        return {
            "excerpt": (getattr(self.obj, "caption", "") or "")[:160],
            "is_completed": getattr(self.obj, "status", "") in ("answered", "not_answered"),
        }