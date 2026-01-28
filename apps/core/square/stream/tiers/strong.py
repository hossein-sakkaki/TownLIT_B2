# apps/core/square/stream/tiers/strong.py

from django.db.models import QuerySet
from .base import StreamTier


class TierStrongRelated(StreamTier):
    """
    Strong semantic relatedness.
    Same owner + same visibility + same subtype.
    """

    name = "strong"
    limit = 5

    def build_queryset(self, *, base_qs, seed, viewer, used_ids) -> QuerySet:
        qs = base_qs.filter(
            content_type=seed.content_type,
            object_id=seed.object_id,
            visibility=seed.visibility,
        )

        # Exclude already used
        if used_ids:
            qs = qs.exclude(id__in=used_ids)

        return qs
