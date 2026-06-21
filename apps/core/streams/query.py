# apps/core/streams/query.py

from django.db.models import Q, QuerySet

from apps.core.visibility.query import VisibilityQuery
from apps.core.owner_visibility.query import OwnerVisibilityQuery
from apps.core.ownership.ownership_filters import exclude_owned_by_viewer
from apps.core.boundaries.query import BoundaryVisibilityQuery

from apps.core.streams.constants import (
    STREAM_SCOPE_SQUARE,
    STREAM_SCOPE_PROFILE,
    STREAM_SCOPE_OWNER,
    STREAM_SCOPE_GLOBAL,
    STREAM_SCOPE_MESSENGER,
)


class StreamQuery:
    """
    Universal stream query builder.

    Important rules:
    - Square scope is discovery mode and must exclude viewer-owned content.
    - Profile scope is profile mode and must keep content from the seed owner,
      including the current viewer's own content.
    - Owner scope is viewer-owned/profile-owned mode.
    - Global scope is unrestricted except visibility gates.
    - Boundary applies to ALL scopes and hides content between bounded users.
    - Stillness does not affect visibility.
    """

    @staticmethod
    def seed_queryset(
        *,
        model,
        viewer,
        scope: str = STREAM_SCOPE_SQUARE,
    ) -> QuerySet:
        """
        Build visible seed queryset.

        The seed must be resolved differently depending on stream scope.

        Square:
            Apply square owner visibility filters.

        Profile / Owner / Global:
            Do NOT apply square-only owner exclusion logic, otherwise opening
            your own profile content as a stream can return 404.

        Boundary:
            Always apply Boundary visibility after normal visibility.
        """

        qs = model.objects.all()

        if scope == STREAM_SCOPE_SQUARE:
            qs = OwnerVisibilityQuery.filter_queryset_for_square(
                qs,
                viewer=viewer,
                kind="stream",
            )

        qs = VisibilityQuery.for_viewer(
            viewer=viewer,
            base_queryset=qs,
        )

        qs = BoundaryVisibilityQuery.exclude_boundary_conflicts(
            qs,
            viewer=viewer,
        )

        return qs

    @staticmethod
    def build(
        *,
        model,
        viewer,
        seed,
        subtype: str,
        scope: str,
        requires_conversion: bool = True,
    ) -> QuerySet:
        """
        Build base stream queryset.

        Ordering and slicing are handled by StreamEngine.
        Boundary filtering must happen before subtype, scope, tiers, and cursor.
        """

        qs = model.objects.all()

        if scope == STREAM_SCOPE_SQUARE:
            qs = OwnerVisibilityQuery.filter_queryset_for_square(
                qs,
                viewer=viewer,
                kind="stream",
            )

        qs = VisibilityQuery.for_viewer(
            viewer=viewer,
            base_queryset=qs,
        )

        qs = BoundaryVisibilityQuery.exclude_boundary_conflicts(
            qs,
            viewer=viewer,
        )

        if requires_conversion and hasattr(model, "is_converted"):
            qs = qs.filter(is_converted=True)

        qs = StreamQuery._filter_by_subtype(
            qs=qs,
            model=model,
            subtype=subtype,
        )

        qs = qs.exclude(id=seed.id)

        qs = StreamQuery._apply_scope(
            qs=qs,
            seed=seed,
            viewer=viewer,
            scope=scope,
        )

        return qs

    @staticmethod
    def _filter_by_subtype(
        *,
        qs: QuerySet,
        model,
        subtype: str,
    ) -> QuerySet:
        """
        Apply subtype filter.
        """

        if hasattr(model, "type"):
            return qs.filter(type=subtype)

        if subtype == "video":
            return qs.filter(video__isnull=False)

        if subtype == "image":
            image_filter = Q(image__isnull=False)

            # Future-safe support for JSON-backed Moment photos.
            try:
                model._meta.get_field("image_items")
                image_filter |= ~Q(image_items=[])
            except Exception:
                pass

            return qs.filter(image_filter)

        return qs
    

    @staticmethod
    def _apply_scope(
        *,
        qs: QuerySet,
        seed,
        viewer,
        scope: str,
    ) -> QuerySet:
        """
        Apply stream scope after visibility/subtype filtering.
        """

        if scope == STREAM_SCOPE_PROFILE:
            return StreamQuery._same_owner(
                qs=qs,
                seed=seed,
            )

        if scope == STREAM_SCOPE_OWNER:
            return StreamQuery._viewer_owned(
                qs=qs,
                seed=seed,
                viewer=viewer,
            )

        if scope == STREAM_SCOPE_SQUARE:
            return exclude_owned_by_viewer(
                qs,
                viewer,
            )

        if scope == STREAM_SCOPE_MESSENGER:
            return qs

        if scope == STREAM_SCOPE_GLOBAL:
            return qs

        return qs.none()

    @staticmethod
    def _same_owner(
        *,
        qs: QuerySet,
        seed,
    ) -> QuerySet:
        """
        Profile stream.

        Keeps only content owned by the same profile owner as the seed.
        This is the correct behavior when a user opens content inside a profile.
        """

        if not hasattr(seed, "content_type") or not hasattr(seed, "object_id"):
            return qs.none()

        return qs.filter(
            content_type=seed.content_type,
            object_id=seed.object_id,
        )

    @staticmethod
    def _viewer_owned(
        *,
        qs: QuerySet,
        seed,
        viewer,
    ) -> QuerySet:
        """
        Owner stream.

        Keeps content from the seed owner, but requires authenticated viewer.
        """

        if not viewer:
            return qs.none()

        if not hasattr(seed, "content_type") or not hasattr(seed, "object_id"):
            return qs.none()

        return qs.filter(
            content_type=seed.content_type,
            object_id=seed.object_id,
        )

    @staticmethod
    def apply_cursor(
        *,
        qs: QuerySet,
        cursor,
    ) -> QuerySet:
        """
        Apply cursor boundary.
        """

        if not cursor:
            return qs

        return qs.filter(
            Q(published_at__lt=cursor.published_at)
            |
            Q(
                published_at=cursor.published_at,
                id__lt=cursor.object_id,
            )
        )