# apps/core/square/stream/serializers.py

from rest_framework import serializers

from apps.posts.serializers.moments import MomentSerializer
from apps.posts.serializers.testimonies import TestimonySerializer
from apps.core.square.stream.dto import StreamItem


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
        serializer_cls = SERIALIZER_MAP.get(item.kind)
        if not serializer_cls:
            return None

        serializer = serializer_cls(
            item.obj,
            context=self.context,
        )
        return serializer.data
