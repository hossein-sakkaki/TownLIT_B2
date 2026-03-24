# apps/core/visibility/query.py

from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from apps.core.visibility.constants import (
    VISIBILITY_GLOBAL,
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
    VISIBILITY_PRIVATE,
)
from apps.profiles.services.active_profile import get_active_profile


class VisibilityQuery:
    """
    Active-profile-aware visibility filtering.
    - Supports Member / Guest / Organization
    - Keeps covenant strictly Member-only
    - Avoids fragile OuterRef/Subquery nesting
    """

    @staticmethod
    def _normalize_viewer(viewer):
        """Anonymous -> None."""
        if not viewer:
            return None
        if getattr(viewer, "is_authenticated", False):
            return viewer
        return None

    @staticmethod
    def for_viewer(*, viewer, base_queryset):
        viewer = VisibilityQuery._normalize_viewer(viewer)

        # -------------------------------------------------
        # 1) Base moderation filters
        # -------------------------------------------------
        qs = base_queryset.filter(
            is_active=True,
            is_hidden=False,
        )

        # -------------------------------------------------
        # 2) Visitor sees only public
        # -------------------------------------------------
        if viewer is None:
            return qs.filter(visibility=VISIBILITY_GLOBAL)

        # Lazy imports
        from apps.profiles.models.member import Member
        from apps.profiles.models.guest import GuestUser
        from apps.profiles.models.relationships import Friendship, Fellowship
        from apps.profilesOrg.models import Organization

        user = viewer
        active = get_active_profile(user)

        member = active.member
        guest = active.guest
        active_profile = active.profile

        member_ct = ContentType.objects.get_for_model(Member)
        guest_ct = ContentType.objects.get_for_model(GuestUser)
        org_ct = ContentType.objects.get_for_model(Organization)

        # -------------------------------------------------
        # 3) Owner access (active profile only)
        # -------------------------------------------------
        owner_q = Q()

        if active_profile:
            active_ct = ContentType.objects.get_for_model(active_profile.__class__)
            owner_q |= Q(
                content_type_id=active_ct.id,
                object_id=active_profile.id,
            )

        # Member-owned organizations stay owner-visible
        if member:
            org_ids = list(
                Organization.objects.filter(
                    org_owners=member
                ).values_list("id", flat=True)
            )
            if org_ids:
                owner_q |= Q(
                    content_type_id=org_ct.id,
                    object_id__in=org_ids,
                )

        # -------------------------------------------------
        # 4) Public visibility
        # -------------------------------------------------
        public_q = Q(visibility=VISIBILITY_GLOBAL)

        # -------------------------------------------------
        # 5) Friend user ids
        # Friendship is user-level, not profile-level
        # -------------------------------------------------
        friendship_rows = Friendship.objects.filter(
            Q(from_user=user) | Q(to_user=user),
            status="accepted",
            is_active=True,
        ).values_list("from_user_id", "to_user_id")

        friend_user_ids = set()
        for from_user_id, to_user_id in friendship_rows:
            if from_user_id == user.id:
                friend_user_ids.add(to_user_id)
            else:
                friend_user_ids.add(from_user_id)

        # -------------------------------------------------
        # 6) Friends visibility
        # Works for Member-owned and Guest-owned content
        # -------------------------------------------------
        friends_q = Q()

        if friend_user_ids:
            member_friend_profile_ids = list(
                Member.objects.filter(
                    user_id__in=friend_user_ids,
                    is_active=True,
                ).values_list("id", flat=True)
            )

            guest_friend_profile_ids = list(
                GuestUser.objects.filter(
                    user_id__in=friend_user_ids,
                    is_active=True,
                ).values_list("id", flat=True)
            )

            member_friends_q = Q()
            guest_friends_q = Q()

            if member_friend_profile_ids:
                member_friends_q = Q(
                    visibility=VISIBILITY_FRIENDS,
                    content_type_id=member_ct.id,
                    object_id__in=member_friend_profile_ids,
                )

            if guest_friend_profile_ids:
                guest_friends_q = Q(
                    visibility=VISIBILITY_FRIENDS,
                    content_type_id=guest_ct.id,
                    object_id__in=guest_friend_profile_ids,
                )

            friends_q = member_friends_q | guest_friends_q

        # -------------------------------------------------
        # 7) Covenant visibility
        # STRICT: Member-only viewer + Member-owned content only
        # -------------------------------------------------
        covenant_q = Q()

        if member:
            fellowship_rows = Fellowship.objects.filter(
                Q(from_user=user) | Q(to_user=user),
                status__iexact="accepted",
            ).values_list("from_user_id", "to_user_id")

            covenant_user_ids = set()
            for from_user_id, to_user_id in fellowship_rows:
                if from_user_id == user.id:
                    covenant_user_ids.add(to_user_id)
                else:
                    covenant_user_ids.add(from_user_id)

            if covenant_user_ids:
                covenant_member_profile_ids = list(
                    Member.objects.filter(
                        user_id__in=covenant_user_ids,
                        is_active=True,
                    ).values_list("id", flat=True)
                )

                if covenant_member_profile_ids:
                    covenant_q = Q(
                        visibility=VISIBILITY_COVENANT,
                        content_type_id=member_ct.id,
                        object_id__in=covenant_member_profile_ids,
                    )

        # -------------------------------------------------
        # 8) Private visibility (owner only)
        # -------------------------------------------------
        private_q = Q(visibility=VISIBILITY_PRIVATE) & owner_q

        # -------------------------------------------------
        # 9) Final filter
        # -------------------------------------------------
        return qs.filter(
            public_q
            | owner_q
            | friends_q
            | covenant_q
            | private_q
        )