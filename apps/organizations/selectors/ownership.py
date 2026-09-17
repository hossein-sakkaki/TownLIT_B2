# apps/organizations/selectors/ownership.py
# TownLIT
#
# Created by Hossein Sakkaki on YYYY-MM-DD.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationRoleKey,
    OrganizationRoleScope,
)
from apps.organizations.models import OrganizationMembership


ORGANIZATION_MANAGER_ROLE_KEYS = (
    OrganizationRoleKey.OWNER,
    OrganizationRoleKey.ADMINISTRATOR,
)


def effective_organization_role_memberships_queryset(
    *,
    role_keys,
    now=None,
):
    now = now or timezone.now()

    normalized_role_keys = tuple(
        dict.fromkeys(
            str(role_key or "").strip()
            for role_key in role_keys
            if str(role_key or "").strip()
        )
    )

    if not normalized_role_keys:
        return OrganizationMembership.objects.none()

    return (
        OrganizationMembership.objects
        .filter(
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
            role_assignments__is_active=True,
            role_assignments__revoked_at__isnull=True,
            role_assignments__starts_at__lte=now,
            role_assignments__role__is_active=True,
            role_assignments__role__key__in=normalized_role_keys,
            role_assignments__scope_type=(
                OrganizationRoleScope.ORGANIZATION
            ),
            role_assignments__scope_key="",
        )
        .filter(
            Q(
                role_assignments__ends_at__isnull=True,
            )
            | Q(
                role_assignments__ends_at__gt=now,
            )
        )
        .distinct()
    )


def effective_organization_owner_memberships_queryset(
    *,
    now=None,
):
    return effective_organization_role_memberships_queryset(
        role_keys=(
            OrganizationRoleKey.OWNER,
        ),
        now=now,
    )


def effective_organization_manager_memberships_queryset(
    *,
    now=None,
):
    return effective_organization_role_memberships_queryset(
        role_keys=ORGANIZATION_MANAGER_ROLE_KEYS,
        now=now,
    )


def effective_organization_manager_user_ids(
    *,
    organization,
    now=None,
) -> set[int]:
    return {
        int(user_id)
        for user_id in (
            effective_organization_manager_memberships_queryset(
                now=now,
            )
            .filter(
                organization=organization,
            )
            .values_list(
                "member__user_id",
                flat=True,
            )
        )
        if user_id
    }