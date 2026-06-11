# apps/core/streams/tiers/base.py

from django.db.models import QuerySet


class StreamTier:
    """
    Base stream tier.
    """

    name: str = "base"
    limit: int = 0

    def build_queryset(
        self,
        *,
        base_qs: QuerySet,
        seed,
        viewer,
        used_ids: set[int],
    ) -> QuerySet:
        raise NotImplementedError