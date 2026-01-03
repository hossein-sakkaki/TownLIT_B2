# apps/core/visibility/query.py

from django.db.models import Q, Exists, OuterRef
from django.contrib.contenttypes.models import ContentType

from apps.core.visibility.constants import (
    VISIBILITY_DEFAULT,
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
    def for_viewer(*, viewer, base_queryset):
        # -------------------------------------------------
        # 1) Base moderation filters (always applied)
        # -------------------------------------------------
        qs = base_queryset.filter(
            is_active=True,
            is_hidden=False,
        )

        # -------------------------------------------------
        # 2) Anonymous viewer
        # -------------------------------------------------
        if not viewer or not viewer.is_authenticated:
            return qs.filter(
                visibility__in=[VISIBILITY_GLOBAL, VISIBILITY_DEFAULT]
            )

        user = viewer

        # -------------------------------------------------
        # 3) Resolve ALL owner identities (polymorphic-safe)
        # -------------------------------------------------
        owner_q = Q()

        member = getattr(user, "member_profile", None)
        guest = getattr(user, "guest_profile", None)

        # ---- Member owner ----
        if member:
            ct = ContentType.objects.get_for_model(member.__class__)
            owner_q |= Q(content_type_id=ct.id, object_id=member.id)

        # ---- Guest owner ----
        if guest:
            ct = ContentType.objects.get_for_model(guest.__class__)
            owner_q |= Q(content_type_id=ct.id, object_id=guest.id)

        # ---- Organization owner (membership-based) ----
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
        # 4) Friends visibility (Member only)
        # -------------------------------------------------
        friends_q = Q()
        if member:
            from apps.profiles.models import Friendship

            friends_q = (
                Q(visibility=VISIBILITY_FRIENDS)
                & Exists(
                    Friendship.objects.filter(
                        is_active=True,
                        status="accepted",
                    ).filter(
                        Q(from_user=member.user, to_user_id=OuterRef("object_id")) |
                        Q(to_user=member.user, from_user_id=OuterRef("object_id"))
                    )
                )
            )

        # -------------------------------------------------
        # 5) Covenant visibility (Member only)
        # -------------------------------------------------
        covenant_q = Q()
        if member:
            from apps.profiles.models import Fellowship

            covenant_q = (
                Q(visibility=VISIBILITY_COVENANT)
                & Exists(
                    Fellowship.objects.filter(
                        status="Accepted",
                    ).filter(
                        Q(from_user=member.user, to_user_id=OuterRef("object_id")) |
                        Q(to_user=member.user, from_user_id=OuterRef("object_id"))
                    )
                )
            )

        # -------------------------------------------------
        # 6) Public visibility
        # -------------------------------------------------
        public_q = Q(
            visibility__in=[VISIBILITY_GLOBAL, VISIBILITY_DEFAULT]
        )

        # -------------------------------------------------
        # 7) Private visibility (owner-only)
        # -------------------------------------------------
        private_q = Q(visibility=VISIBILITY_PRIVATE) & owner_q

        # -------------------------------------------------
        # 8) Final visibility composition
        # -------------------------------------------------
        return qs.filter(
            owner_q |
            private_q |
            public_q |
            friends_q |
            covenant_q
        )
