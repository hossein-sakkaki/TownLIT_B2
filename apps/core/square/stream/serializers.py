# apps/core/square/stream/serializers.py

from rest_framework import serializers

from apps.posts.serializers.moments import MomentSerializer
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.core.square.stream.dto import StreamItem
from apps.core.square.stream.resolvers import resolve_stream_subtype
from apps.core.square.stream.preview import build_stream_preview


SERIALIZER_MAP = {
    "moment": MomentSerializer,
    "testimony": TestimonySerializer,
}


class SquareStreamItemSerializer(serializers.Serializer):
    kind = serializers.CharField()
    id = serializers.IntegerField()
    published_at = serializers.DateTimeField()
    payload = serializers.SerializerMethodField()

    def get_payload(self, item: StreamItem):
        """
        Keep existing payload shape (MomentSerializer/TestimonySerializer),
        but inject payload.preview for fast private CDN rendering.
        """
        serializer_cls = SERIALIZER_MAP.get(item.kind)
        if not serializer_cls:
            return None

        serializer = serializer_cls(item.obj, context=self.context)

        # Copy to mutable dict (Serializer.data can be OrderedDict)
        data = dict(serializer.data)

        # Compute subtype per object (seed/fallback may differ)
        subtype = resolve_stream_subtype(item.obj) or ""

        # Inject preview block (clean CDN URLs; private via signed cookies)
        try:
            data["preview"] = build_stream_preview(item.obj, subtype=subtype)
        except Exception:
            # Fail-safe: never break stream payload
            data["preview"] = {
                "thumbnail_url": None,
                "image_url": None,
                "type": getattr(item.obj, "type", None) if hasattr(item.obj, "type") else None,
                "has_video": bool(getattr(item.obj, "video", None)) if hasattr(item.obj, "video") else False,
            }

        return data
