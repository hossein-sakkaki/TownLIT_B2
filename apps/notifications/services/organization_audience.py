# apps/notifications/services/organization_audience.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-03.
# Last Update by Hossein Sakkaki on 2026-10-03.
#

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationRoleScope,
)
from apps.organizations.models import (
    OrganizationMembership,
    OrganizationRoleAssignment,
)


User = get_user_model()


def users_with_organization_permission(
    *,
    organization,
    permission_key: str,
    scope_type: str = OrganizationRoleScope.ORGANIZATION,
    scope_key: str = "",
    now=None,
):
    """Return real active Organization members holding one permission."""
    now = now or timezone.now()

    assignments = (
        OrganizationRoleAssignment.objects
        .filter(
            membership__organization=organization,
            membership__status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
            membership__member__user__is_active=True,
            membership__member__user__is_deleted=False,
            membership__member__user__is_suspended=False,
            is_active=True,
            revoked_at__isnull=True,
            starts_at__lte=now,
            role__is_active=True,
            role__role_permissions__permission__key=permission_key,
            role__role_permissions__permission__is_active=True,
        )
        .filter(
            Q(ends_at__isnull=True)
            | Q(ends_at__gt=now)
        )
    )

    if scope_type == OrganizationRoleScope.MODULE and scope_key:
        assignments = assignments.filter(
            Q(
                scope_type=OrganizationRoleScope.ORGANIZATION,
                scope_key="",
            )
            | Q(
                scope_type=OrganizationRoleScope.MODULE,
                scope_key=scope_key,
            )
        )
    else:
        assignments = assignments.filter(
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        )

    user_ids = (
        assignments
        .values_list("membership__member__user_id", flat=True)
        .distinct()
    )

    return User.objects.filter(id__in=user_ids).order_by("id")


def user_has_active_organization_membership(*, organization, user) -> bool:
    if not user:
        return False

    return OrganizationMembership.objects.filter(
        organization=organization,
        member__user=user,
        status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    ).exists()
