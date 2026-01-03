# apps/posts/services/feed_access.py
# ======================================================
# Unified visibility-aware feed access (Moment/Testimony)
# ======================================================

from typing import Optional, Type
from django.db.models import QuerySet
from django.contrib.contenttypes.models import ContentType

from apps.core.visibility.query import VisibilityQuery
from apps.posts.models.moment import Moment
from apps.posts.models.testimony import Testimony


POST_MODELS = (Moment, Testimony)


def get_visible_posts(
    model: Type,
    *,
    owner=None,
    viewer=None,
    base_queryset: Optional[QuerySet] = None,
) -> QuerySet:
    """
    Unified access layer for Moment / Testimony.

    Rules:
    - VisibilityPolicy enforced
    - Owner-scoped if owner is provided
    - Viewer-aware (friends / private / self)
    - Counter-ready (denormalized fields preserved)

    Params:
    - model: Moment | Testimony
    - owner: Member | GuestUser | Organization | CustomUser | None
    - viewer: request.user or None
    - base_queryset: optional custom QS override

    Returns:
    - Django QuerySet (NOT evaluated)
    """

    if model not in POST_MODELS:
        raise ValueError(f"Unsupported model: {model}")

    # --------------------------------------------------
    # Base queryset
    # --------------------------------------------------
    qs = base_queryset if base_queryset is not None else model.objects.all()

    # --------------------------------------------------
    # Global safety filters (shared)
    # --------------------------------------------------
    qs = qs.filter(
        is_active=True,
        is_suspended=False,
    )

    # --------------------------------------------------
    # Owner scoping (GenericForeignKey)
    # --------------------------------------------------
    if owner is not None:
        ct = ContentType.objects.get_for_model(owner.__class__)
        qs = qs.filter(
            content_type=ct,
            object_id=owner.id,
        )

    # --------------------------------------------------
    # Visibility enforcement (🔥 CORE VALUE)
    # --------------------------------------------------
    qs = VisibilityQuery.for_viewer(
        viewer=viewer,
        base_queryset=qs,
    )

    # --------------------------------------------------
    # Minimal select/prefetch (safe default)
    # --------------------------------------------------
    qs = qs.select_related("content_type")

    return qs
