from django.db.models import Q, QuerySet
from apps.core.square.stream.tiers.registry import TIERS_BY_KIND


class SquareStreamEngine:
    """
    Tier-based relatedness stream engine.
    """

    @staticmethod
    def apply(
        *,
        queryset: QuerySet,
        seed,
        kind: str,
        viewer,
        cursor: tuple | None,
        limit: int,
        used_ids: set[int] | None = None,
    ) -> list:
        """
        Returns up to `limit` objects.
        If `used_ids` is provided, it is mutated (shared across calls) to avoid duplicates.
        """

        qs = queryset
        results: list = []

        if used_ids is None:
            used_ids = set()

        # -----------------------------
        # Cursor pagination
        # -----------------------------
        if cursor:
            p, last_id = cursor
            qs = qs.filter(
                Q(published_at__lt=p) |
                Q(published_at=p, id__lt=last_id)
            )

        qs = qs.order_by("-published_at", "-id")

        # -----------------------------
        # Tier consumption
        # -----------------------------
        tiers = TIERS_BY_KIND.get(kind, [])

        for tier in tiers:
            if len(results) >= limit:
                break

            tier_qs = tier.build_queryset(
                base_qs=qs,
                seed=seed,
                viewer=viewer,
                used_ids=used_ids,
            )

            batch = list(tier_qs[: tier.limit])

            for obj in batch:
                if obj.id in used_ids:
                    continue
                results.append(obj)
                used_ids.add(obj.id)

            if len(results) >= limit:
                break

        return results[:limit]
