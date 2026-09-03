# apps/organizations/views/access.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from rest_framework.exceptions import NotFound

from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import Organization


def get_visible_organization_or_404(*, user, slug):
    organization = (
        Organization.objects
        .select_related("subscription_account")
        .filter(slug=slug)
        .first()
    )

    if not organization:
        raise NotFound("Organization not found.")

    if getattr(user, "is_staff", False):
        return organization

    is_current_member = organization.memberships.filter(
        member__user=user,
        status__in=CURRENT_MEMBERSHIP_STATUSES,
    ).exists()

    if is_current_member:
        return organization

    is_visible = (
        organization.status == OrganizationStatus.ACTIVE
        and organization.visibility in {
            OrganizationVisibility.PUBLIC,
            OrganizationVisibility.UNLISTED,
        }
    )

    if not is_visible:
        raise NotFound("Organization not found.")

    return organization
