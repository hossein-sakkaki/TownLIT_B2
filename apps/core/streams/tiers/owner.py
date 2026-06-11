# apps/core/streams/tiers/owner.py

from django.db.models import QuerySet

from apps.core.streams.tiers.base import StreamTier


class TierSameOwner(StreamTier):
    """
    Same profile/content owner.
    """

    name = "same_owner"
    limit = 5

    def build_queryset(self, *, base_qs, seed, viewer, used_ids) -> QuerySet:
        if not hasattr(seed, "content_type") or not hasattr(seed, "object_id"):
            return base_qs.none()

        qs = base_qs.filter(
            content_type=seed.content_type,
            object_id=seed.object_id,
        )

        if used_ids:
            qs = qs.exclude(id__in=used_ids)

        return qs