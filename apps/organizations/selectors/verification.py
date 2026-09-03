# apps/organizations/selectors/verification.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationRelationshipStatus,
    OrganizationVerificationGrantStatus,
    OrganizationVerificationGrantType,
)
from apps.organizations.models import OrganizationVerificationGrant


def active_verification_grants_queryset(*, now=None):
    """Return grants whose local validity is currently active."""
    now = now or timezone.now()

    return (
        OrganizationVerificationGrant.objects
        .select_related(
            "relationship__source_organization",
            "verification_case",
        )
        .filter(
            status=OrganizationVerificationGrantStatus.ACTIVE,
            revoked_at__isnull=True,
        )
        .filter(
            Q(expires_at__isnull=True)
            | Q(expires_at__gt=now)
        )
        .filter(
            Q(grant_type=OrganizationVerificationGrantType.DIRECT)
            | Q(
                grant_type=OrganizationVerificationGrantType.SPONSORED_BRANCH,
                relationship__status=OrganizationRelationshipStatus.ACTIVE,
            )
        )
    )


def get_active_verification_grant(
    *,
    organization,
    now=None,
    _visited_organization_ids=None,
):
    """Resolve effective verification, including sponsor validity."""
    now = now or timezone.now()
    visited = set(_visited_organization_ids or ())

    if organization.id in visited:
        return None

    visited.add(organization.id)

    grant = (
        active_verification_grants_queryset(now=now)
        .filter(organization=organization)
        .first()
    )

    if not grant:
        return None

    if grant.grant_type == OrganizationVerificationGrantType.DIRECT:
        return grant

    if not grant.relationship_id:
        return None

    sponsor = grant.relationship.source_organization
    sponsor_grant = get_active_verification_grant(
        organization=sponsor,
        now=now,
        _visited_organization_ids=visited,
    )

    return grant if sponsor_grant else None


def is_organization_verified(*, organization, now=None) -> bool:
    return get_active_verification_grant(
        organization=organization,
        now=now,
    ) is not None


def get_organization_verification_summary(*, organization, now=None):
    grant = get_active_verification_grant(
        organization=organization,
        now=now,
    )

    if not grant:
        return {
            "is_verified": False,
            "grant_type": None,
            "verified_at": None,
            "expires_at": None,
            "authority_organization": None,
        }

    authority = None

    if grant.relationship_id:
        source = grant.relationship.source_organization
        authority = {
            "public_id": str(source.public_id),
            "name": source.name,
            "slug": source.slug,
        }

    return {
        "is_verified": True,
        "grant_type": grant.grant_type,
        "verified_at": grant.granted_at,
        "expires_at": grant.expires_at,
        "authority_organization": authority,
    }
