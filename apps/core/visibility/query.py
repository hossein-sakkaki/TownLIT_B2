# apps/core/visibility/query.py

from django.db.models import Q, Exists, OuterRef
from django.contrib.contenttypes.models import ContentType

from apps.core.visibility.constants import (
    VISIBILITY_GLOBAL,
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
    VISIBILITY_PRIVATE,
)


class VisibilityQuery:
    """
    MySQL-optimized visibility filtering.
    - Polymorphic owner-safe (Member / Guest / Organization)
    - EXISTS-based (no Python loops)
    """

    @staticmethod
    def _normalize_viewer(viewer):
        """Anonymous -> None (authenticated user stays)."""
        if not viewer:
            return None
        if getattr(viewer, "is_authenticated", False):
            return viewer
        return None

    @staticmethod
    def for_viewer(*, viewer, base_queryset):
        viewer = VisibilityQuery._normalize_viewer(viewer)

        # -------------------------------------------------
        # 1) Base moderation filters (always applied)
        # -------------------------------------------------
        qs = base_queryset.filter(
            is_active=True,
            is_hidden=False,
        )

        # -------------------------------------------------
        # 2) Visitor (unauthenticated):
        #    ONLY public content is visible
        # -------------------------------------------------
        if viewer is None:
            return qs.filter(visibility=VISIBILITY_GLOBAL)

        user = viewer

        # -------------------------------------------------
        # 3) Resolve owner identities (polymorphic-safe)
        # -------------------------------------------------
        owner_q = Q()

        member = getattr(user, "member_profile", None)
        guest = getattr(user, "guest_profile", None)

        # Member-owned content
        if member:
            ct = ContentType.objects.get_for_model(member.__class__)
            owner_q |= Q(content_type_id=ct.id, object_id=member.id)

        # Guest-owned content
        if guest:
            ct = ContentType.objects.get_for_model(guest.__class__)
            owner_q |= Q(content_type_id=ct.id, object_id=guest.id)

        # Organization-owned content (via membership)
        if member:
            from apps.profilesOrg.models import Organization

            org_ids = Organization.objects.filter(
                org_owners=member
            ).values_list("id", flat=True)

            if org_ids:
                org_ct = ContentType.objects.get_for_model(Organization)
                owner_q |= Q(
                    content_type_id=org_ct.id,
                    object_id__in=org_ids,
                )

        # -------------------------------------------------
        # 4) Public visibility (GLOBAL)
        # -------------------------------------------------
        public_q = Q(
            visibility__in=[VISIBILITY_GLOBAL]
        )

        # -------------------------------------------------
        # 5) Friends visibility (Member only)
        # -------------------------------------------------
        friends_q = Q()
        if member:
            from apps.profiles.models import Friendship

            friends_q = (
                Q(visibility=VISIBILITY_FRIENDS)
                &
                Exists(
                    Friendship.objects.filter(
                        status="accepted",
                        is_active=True,
                    ).filter(
                        Q(from_user=member.user, to_user_id=OuterRef("object_id")) |
                        Q(to_user=member.user, from_user_id=OuterRef("object_id"))
                    )
                )
            )

        # -------------------------------------------------
        # 6) Covenant visibility (Member only, STRICT)
        # -------------------------------------------------
        covenant_q = Q()
        if member:
            from apps.profiles.models import Fellowship, Member

            member_ct = ContentType.objects.get_for_model(Member)

            covenant_q = (
                Q(visibility=VISIBILITY_COVENANT)
                &
                Q(content_type_id=member_ct.id)
                &
                Exists(
                    Fellowship.objects.filter(
                        status="Accepted",
                    ).filter(
                        Q(from_user=member.user, to_user_id=OuterRef("object_id")) |
                        Q(to_user=member.user, from_user_id=OuterRef("object_id"))
                    )
                )
            )

        # -------------------------------------------------
        # 7) Private visibility (owner only)
        # -------------------------------------------------
        private_q = Q(visibility=VISIBILITY_PRIVATE) & owner_q

        # -------------------------------------------------
        # 8) Final composition
        #    (EXCLUSIVE visibility paths)
        # -------------------------------------------------
        return qs.filter(
            public_q
            | owner_q
            | friends_q
            | covenant_q
            | private_q
        )
