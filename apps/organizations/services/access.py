# apps/organizations/services/access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationRoleScope,
)
from apps.organizations.models import OrganizationMembership


def get_current_membership_for_user(*, organization, user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    return (
        OrganizationMembership.objects
        .select_related(
            "member__user",
            "organization",
        )
        .filter(
            organization=organization,
            member__user=user,
            status__in=CURRENT_MEMBERSHIP_STATUSES,
        )
        .first()
    )


def user_has_organization_permission(
    *,
    user,
    organization,
    permission_key,
    scope_type=OrganizationRoleScope.ORGANIZATION,
    scope_key="",
    now=None,
) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_staff", False):
        return True

    membership = get_current_membership_for_user(
        organization=organization,
        user=user,
    )

    if not membership:
        return False

    if membership.status not in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES:
        return False

    now = now or timezone.now()

    assignments = membership.role_assignments.filter(
        is_active=True,
        revoked_at__isnull=True,
        starts_at__lte=now,
        role__is_active=True,
        role__role_permissions__permission__key=permission_key,
        role__role_permissions__permission__is_active=True,
    ).filter(
        Q(ends_at__isnull=True)
        | Q(ends_at__gt=now)
    )

    if scope_type == OrganizationRoleScope.ORGANIZATION:
        return assignments.filter(
            scope_type=OrganizationRoleScope.ORGANIZATION,
            scope_key="",
        ).exists()

    if scope_type == OrganizationRoleScope.MODULE:
        return assignments.filter(
            Q(
                scope_type=OrganizationRoleScope.ORGANIZATION,
                scope_key="",
            )
            | Q(
                scope_type=OrganizationRoleScope.MODULE,
                scope_key=scope_key,
            )
        ).exists()

    return False


def organization_ids_for_user_permission(
    *,
    user,
    permission_key,
    now=None,
):
    if not user or not getattr(user, "is_authenticated", False):
        return []

    if getattr(user, "is_staff", False):
        from apps.organizations.models import Organization

        return Organization.objects.values_list("id", flat=True)

    now = now or timezone.now()

    return (
        OrganizationMembership.objects
        .filter(
            member__user=user,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
            role_assignments__is_active=True,
            role_assignments__revoked_at__isnull=True,
            role_assignments__starts_at__lte=now,
            role_assignments__role__is_active=True,
            role_assignments__role__role_permissions__permission__key=(
                permission_key
            ),
            role_assignments__role__role_permissions__permission__is_active=True,
        )
        .filter(
            Q(role_assignments__ends_at__isnull=True)
            | Q(role_assignments__ends_at__gt=now)
        )
        .values_list("organization_id", flat=True)
        .distinct()
    )
