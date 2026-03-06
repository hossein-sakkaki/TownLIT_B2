# apps/core/square/stream/serializers.py

from rest_framework import serializers

from apps.posts.serializers.moments import MomentSerializer
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.posts.serializers.prayers import PrayerSerializer

from apps.posts.models.pray import PrayerResponse  # ✅ add

from apps.core.square.stream.dto import StreamItem
from apps.core.square.stream.resolvers import resolve_stream_subtype
from apps.core.square.stream.preview import build_stream_preview


SERIALIZER_MAP = {
    "moment": MomentSerializer,
    "testimony": TestimonySerializer,
    "pray": PrayerSerializer,
}


class SquareStreamItemSerializer(serializers.Serializer):
    kind = serializers.CharField()
    id = serializers.IntegerField()
    published_at = serializers.DateTimeField()
    payload = serializers.SerializerMethodField()

    def _safe_preview_for(self, obj, *, subtype: str) -> dict:
        try:
            return build_stream_preview(obj, subtype=subtype)
        except Exception:
            return {
                "thumbnail_url": None,
                "image_url": None,
                "type": getattr(obj, "type", None) if hasattr(obj, "type") else None,
                "has_video": bool(getattr(obj, "video", None)) if hasattr(obj, "video") else False,
            }

    def get_payload(self, item: StreamItem):
        serializer_cls = SERIALIZER_MAP.get(item.kind)
        if not serializer_cls:
            return None

        serializer = serializer_cls(item.obj, context=self.context)

        # If serializer returns None (gated), keep stream safe
        raw = serializer.data
        if raw is None:
            return None

        data = dict(raw)

        # Subtype for main object
        subtype = resolve_stream_subtype(item.obj) or ""

        # Inject preview for main object
        data["preview"] = self._safe_preview_for(item.obj, subtype=subtype)

        # -------------------------------------------------
        # ✅ Prayer: ensure response payload exists + preview
        # -------------------------------------------------
        if item.kind == "pray":
            resp = getattr(item.obj, "response", None)

            # Always send "response" key (null when waiting)
            if not resp:
                data["response"] = None
            else:
                # PrayerResponse subtype (video/image)
                resp_subtype = "video" if getattr(resp, "video", None) else "image"

                # Ensure nested response dict exists
                resp_data = data.get("response") or {}
                if isinstance(resp_data, dict):
                    # Inject preview for response media
                    resp_data["preview"] = self._safe_preview_for(resp, subtype=resp_subtype)
                    data["response"] = resp_data
                else:
                    # If for any reason it wasn't a dict, normalize
                    data["response"] = {
                        "id": getattr(resp, "id", None),
                        "result_status": getattr(resp, "result_status", None),
                        "response_text": getattr(resp, "response_text", None),
                        "preview": self._safe_preview_for(resp, subtype=resp_subtype),
                    }

        return data