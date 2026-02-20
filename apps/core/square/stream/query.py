# apps/core/square/stream/query.py

from django.db.models import QuerySet

from apps.core.visibility.query import VisibilityQuery
from apps.core.owner_visibility.query import OwnerVisibilityQuery
from apps.core.ownership.ownership_filters import exclude_owned_by_viewer


class SquareStreamQuery:
    """
    Base queryset builder for Square stream.

    Applies ONLY domain-level filters:
    - owner eligibility
    - visibility
    - availability
    - subtype
    - ownership (exclude viewer's own content)

    NO ordering.
    NO slicing.
    """

    @staticmethod
    def build(
        *,
        model,
        viewer,
        subtype: str,
        seed,
    ) -> QuerySet:
        qs = model.objects.all()

        # -------------------------------------------------
        # 🔥 1) OWNER ELIGIBILITY (account state)
        # -------------------------------------------------
        qs = OwnerVisibilityQuery.filter_queryset_for_square(
            qs,
            viewer=viewer,
            kind="stream",  # behaves like ALL but without privacy promotion
        )

        # -------------------------------------------------
        # 2) Visibility (friends / public / etc.)
        # -------------------------------------------------
        qs = VisibilityQuery.for_viewer(viewer=viewer, base_queryset=qs)

        # -------------------------------------------------
        # 3) Availability (converted / written)
        # -------------------------------------------------
        qs = qs.filter(is_converted=True)

        # -------------------------------------------------
        # 4) Subtype filtering (model-specific)
        # -------------------------------------------------
        if hasattr(model, "type"):
            qs = qs.filter(type=subtype)
        else:
            if subtype == "video":
                qs = qs.filter(video__isnull=False)
            elif subtype == "image":
                qs = qs.filter(image__isnull=False)

        # -------------------------------------------------
        # 5) Exclude seed itself
        # -------------------------------------------------
        qs = qs.exclude(id=seed.id)

        # -------------------------------------------------
        # 6) Exclude viewer's own content
        # -------------------------------------------------
        qs = exclude_owned_by_viewer(qs, viewer)

        return qs