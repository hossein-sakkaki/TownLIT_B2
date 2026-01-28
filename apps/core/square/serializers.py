# apps/core/square/serializers.py
import logging
from rest_framework import serializers

from apps.posts.serializers.moments import MomentSerializer
from apps.posts.serializers.testimonies import TestimonySerializer
logger = logging.getLogger(__name__)


SERIALIZER_MAP = {
    "moment": MomentSerializer,
    "testimony": TestimonySerializer,
    # "pray": PraySerializer (future)
}


class SquareItemSerializer(serializers.Serializer):
    """
    Square wrapper serializer.

    Delegates media/security logic to the ORIGINAL serializers
    (MomentSerializer, TestimonySerializer, ...)

    Square does NOT touch:
    - S3 signing
    - media conversion gating
    - visibility hardening
    """

    square_kind = serializers.CharField()

    payload = serializers.SerializerMethodField()

    def get_payload(self, obj):
        """
        Returns normalized payload produced by the original serializer.
        """
        kind = getattr(obj, "square_kind", None)
        if not kind:
            return None

        serializer_cls = SERIALIZER_MAP.get(kind)
        if not serializer_cls:
            return None

        serializer = serializer_cls(
            obj,
            context=self.context,
        )

        data = serializer.data

        # 🔐 IMPORTANT:
        # Some serializers may return None (e.g. media not allowed)
        if not data:
            return None

        return data

    def to_representation(self, obj):
        """
        Final Square output.
        """
        payload = self.get_payload(obj)
        if payload is None:
            return None

        return {
            "kind": obj.square_kind,
            "id": obj.id,
            "published_at": getattr(obj, "published_at", None),
            "payload": payload,
        }
