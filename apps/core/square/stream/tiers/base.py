# apps/core/square/stream/tiers/base.py

from django.db.models import QuerySet


class StreamTier:
    """
    Base class for relatedness tiers.
    Each tier contributes a LIMITED number of items.
    """

    name: str = "base"
    limit: int = 0  # max items this tier can contribute

    def build_queryset(
        self,
        *,
        base_qs: QuerySet,
        seed,
        viewer,
        used_ids: set[int],
    ) -> QuerySet:
        raise NotImplementedError
