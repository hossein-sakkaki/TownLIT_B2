# apps/core/boundaries/query.py

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.core.boundaries.constants import BOUNDARY_BOUNDARY
from apps.core.boundaries.models import UserBoundary
from apps.profiles.models import Member, GuestUser
from apps.profilesOrg.models import Organization


class BoundaryVisibilityQuery:
    """
    Query-level visibility filter for TownLIT Boundary.

    Product rule:
    - Stillness does NOT hide feed/stream/search content.
    - Boundary DOES hide content between the two users in both directions.

    This layer is intentionally query-level so blocked content never reaches:
    - ranking
    - stream tiers
    - cursor pagination
    - serializers
    - previews
    """

    @staticmethod
    def exclude_boundary_conflicts(qs: QuerySet, *, viewer) -> QuerySet:
        """
        Exclude rows owned by users who have Boundary with viewer
        in either direction.

        Supports:
        1) Generic owner fields: content_type + object_id
           - Member owner
           - GuestUser owner
           - Organization owner through org_owners.user

        2) Direct user FK fields, if present:
           - user
           - name
           - owner
           - author
           - created_by
        """

        if not viewer or not getattr(viewer, "is_authenticated", False):
            return qs

        model = qs.model
        field_names = {field.name for field in model._meta.get_fields()}

        # GenericForeignKey ownership pattern used by post-like models.
        if "content_type" in field_names and "object_id" in field_names:
            qs = BoundaryVisibilityQuery._exclude_gfk_owner_conflicts(
                qs,
                viewer=viewer,
            )

        # Direct user FK ownership patterns.
        direct_user_fields = [
            "user",
            "name",
            "owner",
            "author",
            "created_by",
            "member_user",
            "org_owner_user",
        ]

        for field_name in direct_user_fields:
            if field_name in field_names:
                qs = BoundaryVisibilityQuery._exclude_direct_user_conflicts(
                    qs,
                    viewer=viewer,
                    field_name=field_name,
                )

        return qs

    @staticmethod
    def _boundary_exists_for_user_id(*, viewer, user_id_outer_ref):
        """
        Boundary in either direction:
        - viewer set Boundary toward owner
        - owner set Boundary toward viewer
        """

        return UserBoundary.objects.filter(
            boundary_type=BOUNDARY_BOUNDARY,
            is_active=True,
        ).filter(
            Q(owner=viewer, target_id=user_id_outer_ref)
            |
            Q(owner_id=user_id_outer_ref, target=viewer)
        )

    @staticmethod
    def _exclude_direct_user_conflicts(
        qs: QuerySet,
        *,
        viewer,
        field_name: str,
    ) -> QuerySet:
        """
        Exclude objects with a direct user FK if that user has Boundary
        with viewer.
        """

        user_id_field = f"{field_name}_id"

        boundary_exists = BoundaryVisibilityQuery._boundary_exists_for_user_id(
            viewer=viewer,
            user_id_outer_ref=OuterRef(user_id_field),
        )

        return qs.exclude(
            Exists(boundary_exists)
        )

    @staticmethod
    def _exclude_gfk_owner_conflicts(
        qs: QuerySet,
        *,
        viewer,
    ) -> QuerySet:
        """
        Exclude GenericForeignKey-owned content when owner has Boundary
        with viewer.
        """

        member_ct = ContentType.objects.get_for_model(Member)
        guest_ct = ContentType.objects.get_for_model(GuestUser)
        org_ct = ContentType.objects.get_for_model(Organization)

        # ------------------------------------------------------------
        # Member-owned content
        # ------------------------------------------------------------
        member_owner_with_boundary = Member.objects.filter(
            id=OuterRef("object_id"),
        ).filter(
            Exists(
                BoundaryVisibilityQuery._boundary_exists_for_user_id(
                    viewer=viewer,
                    user_id_outer_ref=OuterRef("user_id"),
                )
            )
        )

        qs = qs.exclude(
            Q(content_type_id=member_ct.id)
            &
            Exists(member_owner_with_boundary)
        )

        # ------------------------------------------------------------
        # Guest-owned content
        # ------------------------------------------------------------
        guest_owner_with_boundary = GuestUser.objects.filter(
            id=OuterRef("object_id"),
        ).filter(
            Exists(
                BoundaryVisibilityQuery._boundary_exists_for_user_id(
                    viewer=viewer,
                    user_id_outer_ref=OuterRef("user_id"),
                )
            )
        )

        qs = qs.exclude(
            Q(content_type_id=guest_ct.id)
            &
            Exists(guest_owner_with_boundary)
        )

        # ------------------------------------------------------------
        # Organization-owned content
        # ------------------------------------------------------------
        # If any active organization owner has Boundary with viewer,
        # hide that organization content from this viewer.
        org_owner_with_boundary = Organization.objects.filter(
            id=OuterRef("object_id"),
            org_owners__is_active=True,
            org_owners__user__isnull=False,
        ).filter(
            Exists(
                BoundaryVisibilityQuery._boundary_exists_for_user_id(
                    viewer=viewer,
                    user_id_outer_ref=OuterRef("org_owners__user_id"),
                )
            )
        )

        qs = qs.exclude(
            Q(content_type_id=org_ct.id)
            &
            Exists(org_owner_with_boundary)
        )

        return qs