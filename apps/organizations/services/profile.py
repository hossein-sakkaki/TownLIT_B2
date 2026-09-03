# apps/organizations/services/profile.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationPermissionKey,
)
from apps.organizations.models import (
    Organization,
    OrganizationAuditLog,
)
from apps.organizations.services.access import (
    user_has_organization_permission,
)


@transaction.atomic
def update_organization_profile(
    *,
    organization,
    actor,
    validated_data,
):
    organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )

    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=OrganizationPermissionKey.MANAGE_PROFILE,
    ):
        raise PermissionDenied(
            "You do not have permission to manage this organization profile."
        )

    immutable_fields = {
        "id",
        "public_id",
        "slug",
        "subscription_account",
        "created_by",
        "status",
        "suspended_at",
        "closed_at",
    }

    changed_fields = []

    for field, value in validated_data.items():
        if field in immutable_fields:
            continue

        setattr(organization, field, value)
        changed_fields.append(field)

    organization.full_clean()
    organization.save()

    OrganizationAuditLog.objects.create(
        organization=organization,
        action=OrganizationAuditAction.ORGANIZATION_UPDATED,
        source=OrganizationAuditSource.SERVICE,
        actor=actor,
        metadata={
            "fields": sorted(set(changed_fields)),
        },
    )

    return organization
