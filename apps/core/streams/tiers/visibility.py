# apps/core/streams/tiers/visibility.py

from django.db.models import QuerySet

from apps.core.streams.tiers.base import StreamTier


class TierSameVisibility(StreamTier):
    """
    Same visibility, not necessarily same owner.
    """

    name = "same_visibility"
    limit = 5

    def build_queryset(self, *, base_qs, seed, viewer, used_ids) -> QuerySet:
        qs = base_qs.filter(
            visibility=getattr(seed, "visibility", None),
        )

        if used_ids:
            qs = qs.exclude(id__in=used_ids)

        return qs