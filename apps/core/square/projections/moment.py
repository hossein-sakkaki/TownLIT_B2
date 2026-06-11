# apps/core/square/projections/moment.py

from .base import SquareProjection
from .registry import register_projection
from .media import safe_preview_key, cdn_url


@register_projection("moment")
class MomentSquareProjection(SquareProjection):
    """
    Lightweight Square projection for Moments.

    Supports:
    - legacy single-photo Moments
    - video Moments with thumbnail
    - JSON-backed multi-photo Moments

    Important:
    - iOS can resolve image_items through field_name.
    - Web Square grid needs cdn_url/image_url for each image item.
    """

    def get_preview(self):
        obj = self.obj

        is_video = bool(getattr(obj, "video", None))

        if is_video:
            thumb_key = safe_preview_key(obj, "thumbnail")
            thumb_url = cdn_url(thumb_key)

            return {
                "thumbnail_url": thumb_url,
                "image_url": None,
                "poster_url": thumb_url,
                "has_video": True,
                "type": "video",
                "media_kind": "video",

                # Photo metadata is intentionally empty for video Moments.
                "image_items": [],
                "cover_image_id": None,
                "cover_image": None,
            }

        image_items = self._get_image_items_payload(obj)
        cover_image = self._get_cover_image_payload(obj, image_items)

        # Backward-compatible preview URL.
        # For multi-photo Moments, this points to the pinned/cover image.
        cover_key = self._get_cover_key(obj)
        image_key = cover_key or safe_preview_key(obj, "image")
        image_url = cdn_url(image_key)

        # If cover image payload has URL, prefer it for Square preview.
        cover_url = None
        if isinstance(cover_image, dict):
            cover_url = (
                cover_image.get("cdn_url")
                or cover_image.get("image_url")
                or cover_image.get("url")
            )

        final_image_url = cover_url or image_url

        return {
            "thumbnail_url": None,
            "image_url": final_image_url,
            "poster_url": final_image_url,
            "has_video": False,
            "type": "image",
            "media_kind": "image",

            # New multi-photo metadata for iOS/web Square grid.
            "image_items": image_items,
            "cover_image_id": getattr(obj, "cover_image_id", None),
            "cover_image": cover_image,
        }

    def get_meta(self):
        """
        Moment has no title field.
        """
        return {
            "excerpt": (getattr(self.obj, "caption", "") or "")[:160],
        }

    # ---------------------------------------------------------
    # Multi-photo helpers
    # ---------------------------------------------------------

    def _get_ordered_items(self, obj):
        """
        Return normalized ordered image items.
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

    def _get_cover_key(self, obj):
        """
        Resolve pinned cover key without media signing.
        """
        try:
            if hasattr(obj, "cover_image_key"):
                return obj.cover_image_key()

            items = self._get_ordered_items(obj)
            if not items:
                return None

            cover_id = str(getattr(obj, "cover_image_id", "") or "")

            if cover_id:
                for item in items:
                    if str(item.get("id")) == cover_id:
                        return str(item.get("key") or "").lstrip("/") or None

            return str(items[0].get("key") or "").lstrip("/") or None

        except Exception:
            return None

    def _get_image_items_payload(self, obj):
        """
        Return lightweight image item metadata for Square clients.

        Web needs cdn_url/image_url.
        iOS needs field_name.
        """
        items = self._get_ordered_items(obj)
        cover_id = str(getattr(obj, "cover_image_id", "") or "")

        payload = []

        for index, item in enumerate(items):
            item_id = str(item.get("id") or "").strip()
            key = str(item.get("key") or "").strip().lstrip("/")

            if not item_id or not key:
                continue

            item_url = cdn_url(key)

            payload.append({
                "id": item_id,
                "key": key,
                "order": int(item.get("order", index) or index),
                "file_name": item.get("file_name") or key.split("/")[-1],
                "mime_type": item.get("mime_type") or "",
                "size": int(item.get("size") or 0),
                "is_cover": item_id == cover_id or bool(item.get("is_cover")),

                # iOS / asset resolver.
                "field_name": f"image_items:{item_id}",

                # Web Square grid.
                "cdn_url": item_url,
                "image_url": item_url,
                "url": item_url,
            })

        return payload

    def _get_cover_image_payload(self, obj, image_items):
        """
        Return cover descriptor for Square clients.
        """
        if not image_items:
            if getattr(obj, "image", None):
                image_key = safe_preview_key(obj, "image")
                image_url = cdn_url(image_key)

                return {
                    "id": None,
                    "field_name": "image",
                    "source": "image",
                    "cdn_url": image_url,
                    "image_url": image_url,
                    "url": image_url,
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
                        "url": item.get("url"),
                    }

        first = image_items[0]

        return {
            "id": first["id"],
            "field_name": first["field_name"],
            "source": "image_items",
            "cdn_url": first.get("cdn_url"),
            "image_url": first.get("image_url"),
            "url": first.get("url"),
        }