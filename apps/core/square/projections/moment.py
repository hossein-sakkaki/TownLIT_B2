# apps/core/square/projections/moment.py

from .base import SquareProjection
from .registry import register_projection
from .media import safe_preview_key, cdn_url


@register_projection("moment")
class MomentSquareProjection(SquareProjection):

    def get_preview(self):
        obj = self.obj

        thumb_key = safe_preview_key(obj, "thumbnail")
        image_key = safe_preview_key(obj, "image")

        return {
            "thumbnail_url": cdn_url(thumb_key),
            "image_url": cdn_url(image_key),
            "has_video": bool(getattr(obj, "video", None)),
        }

    def get_meta(self):
        return {
            "title": (getattr(self.obj, "title", "") or "")[:120],
            "excerpt": (getattr(self.obj, "caption", "") or "")[:160],
        }
