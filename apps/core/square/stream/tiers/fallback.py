from django.db.models import QuerySet
from .base import StreamTier


class TierSameTypeFallback(StreamTier):
    """
    Fallback: same subtype only.
    No semantic relation.
    """

    name = "fallback"
    limit = 10

    def build_queryset(self, *, base_qs, seed, viewer, used_ids) -> QuerySet:
        qs = base_qs

        if used_ids:
            qs = qs.exclude(id__in=used_ids)

        return qs
