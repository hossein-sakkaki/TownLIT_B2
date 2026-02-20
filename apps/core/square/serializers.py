# apps/core/square/serializers.py

from rest_framework import serializers
from apps.core.square.projections.registry import get_projection
import logging

logger = logging.getLogger(__name__)


class SquareItemSerializer(serializers.Serializer):

    def to_representation(self, obj):
        try:
            kind = getattr(obj, "square_kind", None)
            if not kind:
                return None

            projection_cls = get_projection(kind)
            if not projection_cls:
                logger.warning("No projection for kind=%s", kind)
                return None

            projection = projection_cls(
                obj,
                request=self.context.get("request"),
                viewer=getattr(self.context.get("request"), "user", None),
            )

            return projection.serialize()

        except Exception:
            logger.exception("Square projection failed for obj id=%s kind=%s", getattr(obj, "id", None), getattr(obj, "square_kind", None))
            return None

