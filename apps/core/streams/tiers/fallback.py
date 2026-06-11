# apps/core/streams/tiers/fallback.py

from django.db.models import QuerySet

from apps.core.streams.tiers.base import StreamTier


class TierFallback(StreamTier):
    """
    Final fallback tier.
    """

    name = "fallback"
    limit = 10

    def build_queryset(self, *, base_qs, seed, viewer, used_ids) -> QuerySet:
        qs = base_qs

        if used_ids:
            qs = qs.exclude(id__in=used_ids)

        return qs