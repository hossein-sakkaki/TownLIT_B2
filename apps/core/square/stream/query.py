# apps/core/square/stream/query.py

from django.db.models import QuerySet

from apps.core.visibility.query import VisibilityQuery
from apps.core.ownership.ownership_filters import exclude_owned_by_viewer


class SquareStreamQuery:
    """
    Base queryset builder for Square stream.

    Applies ONLY domain-level filters:
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
        # Visibility (friends / public / etc.)
        # -------------------------------------------------
        qs = VisibilityQuery.for_viewer(
            viewer=viewer,
            base_queryset=qs,
        )

        # -------------------------------------------------
        # Availability (converted / written)
        # -------------------------------------------------
        qs = qs.filter(is_converted=True)

        # -------------------------------------------------
        # Subtype filtering (model-specific)
        # -------------------------------------------------
        if hasattr(model, "type"):
            # Testimony
            qs = qs.filter(type=subtype)
        else:
            # Moment
            if subtype == "video":
                qs = qs.filter(video__isnull=False)
            elif subtype == "image":
                qs = qs.filter(image__isnull=False)

        # -------------------------------------------------
        # Exclude seed itself
        # -------------------------------------------------
        qs = qs.exclude(id=seed.id)

        # -------------------------------------------------
        # 🔥 Exclude viewer's own content (Square UX rule)
        # -------------------------------------------------
        qs = exclude_owned_by_viewer(qs, viewer)

        return qs
