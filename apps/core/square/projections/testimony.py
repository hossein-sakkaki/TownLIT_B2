# apps/core/square/projections/testimony.py

from .base import SquareProjection
from .registry import register_projection
from .media import safe_preview_key, cdn_url


@register_projection("testimony")
class TestimonySquareProjection(SquareProjection):

    def get_preview(self):
        obj = self.obj

        thumb_key = safe_preview_key(obj, "thumbnail")
        image_key = safe_preview_key(obj, "image")

        return {
            "thumbnail_url": cdn_url(thumb_key),
            "image_url": cdn_url(image_key),
            "type": getattr(obj, "type", "written"),
        }

    def get_meta(self):
        return {
            "title": (getattr(self.obj, "title", "") or "")[:120],
            "excerpt": (getattr(self.obj, "content", "") or "")[:160],
        }
