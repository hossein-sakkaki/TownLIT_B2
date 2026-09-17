# apps/core/owner_visibility/query.py

from django.db.models import Q, Exists, OuterRef
from django.contrib.contenttypes.models import ContentType

from apps.organizations.constants import (
    OrganizationStatus,
)
from apps.organizations.models import Organization
from apps.organizations.selectors.ownership import (
    effective_organization_owner_memberships_queryset,
)
from apps.profiles.models import (
    Friendship,
    Member,
)


class OwnerVisibilityQuery:

    @staticmethod
    def filter_queryset_for_square(qs, *, viewer, kind):

        member_ct = ContentType.objects.get_for_model(Member)
        org_ct = ContentType.objects.get_for_model(Organization)

        # -------------------------------------------------
        # 1) HARD BLOCK
        # -------------------------------------------------
        active_member_owner = Member.objects.filter(
            id=OuterRef("object_id"),
            is_active=True,
            is_hidden_by_confidants=False,
            user__is_deleted=False,
            user__is_suspended=False,
            user__is_account_paused=False,
        )

        qs = qs.exclude(
            Q(content_type_id=member_ct.id) &
            ~Exists(active_member_owner)
        )

        # -------------------------------------------------
        # 2) PRIVACY (friends only)
        # -------------------------------------------------
        if viewer and viewer.is_authenticated:

            # owner member
            owner_member = Member.objects.filter(
                id=OuterRef("object_id"),
                is_privacy=True,
            )

            # friendship between viewer and owner.user
            friend_of_owner = Member.objects.filter(
                id=OuterRef("object_id")
            ).filter(
                Exists(
                    Friendship.objects.filter(
                        status="accepted",
                        is_active=True,
                    ).filter(
                        Q(from_user=viewer, to_user=OuterRef("user")) |
                        Q(to_user=viewer, from_user=OuterRef("user"))
                    )
                )
            )

            qs = qs.exclude(
                Q(content_type_id=member_ct.id) &
                Exists(owner_member) &
                ~Exists(friend_of_owner)
            )

        else:
            qs = qs.exclude(
                Q(content_type_id=member_ct.id) &
                Exists(Member.objects.filter(id=OuterRef("object_id"), is_privacy=True))
            )

        # -------------------------------------------------
        # 3) ORGANIZATION
        # -------------------------------------------------
        active_org_owner = (
            effective_organization_owner_memberships_queryset()
            .filter(
                organization_id=OuterRef("object_id"),
                organization__status=OrganizationStatus.ACTIVE,
                member__is_active=True,
                member__is_hidden_by_confidants=False,
                member__user__is_deleted=False,
                member__user__is_suspended=False,
                member__user__is_account_paused=False,
            )
        )

        qs = qs.exclude(
            Q(content_type_id=org_ct.id)
            & ~Exists(active_org_owner)
        )

        return qs