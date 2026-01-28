# apps/core/square/stream/tiers/weak.py

from django.db.models import QuerySet
from .base import StreamTier


class TierWeakRelated(StreamTier):
    """
    Same subtype, different owner.
    """

    name = "weak"
    limit = 5

    def build_queryset(self, *, base_qs, seed, viewer, used_ids) -> QuerySet:
        qs = base_qs.exclude(
            content_type=seed.content_type,
            object_id=seed.object_id,
        )

        if used_ids:
            qs = qs.exclude(id__in=used_ids)

        return qs
