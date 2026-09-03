# apps/organizations/services/eligibility.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.organizations.feature_flags import (
    ensure_organization_creation_enabled,
)


@dataclass(frozen=True)
class OrganizationCreationEligibility:
    eligible: bool
    code: str
    detail: str


def get_organization_creation_eligibility(
    user,
) -> OrganizationCreationEligibility:
    if not user or not getattr(user, "is_authenticated", False):
        return OrganizationCreationEligibility(
            False,
            "authentication_required",
            "Authentication is required.",
        )

    if not getattr(user, "is_active", False):
        return OrganizationCreationEligibility(
            False,
            "account_inactive",
            "The account is not active.",
        )

    if getattr(user, "is_deleted", False):
        return OrganizationCreationEligibility(
            False,
            "account_deleted",
            "The account is deactivated.",
        )

    if getattr(user, "is_suspended", False):
        return OrganizationCreationEligibility(
            False,
            "account_suspended",
            "The account is suspended.",
        )

    if getattr(user, "is_account_paused", False):
        return OrganizationCreationEligibility(
            False,
            "account_paused",
            "The account is paused.",
        )

    if not getattr(user, "is_member", False):
        return OrganizationCreationEligibility(
            False,
            "member_required",
            "Only TownLIT Members can create organizations.",
        )

    member = getattr(user, "member_profile", None)

    if not member or not getattr(member, "is_active", False):
        return OrganizationCreationEligibility(
            False,
            "active_member_profile_required",
            "An active TownLIT Member profile is required.",
        )

    if not getattr(user, "is_verified_identity", False):
        return OrganizationCreationEligibility(
            False,
            "identity_verification_required",
            "Identity verification is required.",
        )

    if not getattr(member, "is_townlit_verified", False):
        return OrganizationCreationEligibility(
            False,
            "townlit_verification_required",
            "TownLIT verification is required.",
        )

    return OrganizationCreationEligibility(
        True,
        "eligible",
        "The member can create an organization.",
    )


def ensure_user_can_create_organization(user):
    ensure_organization_creation_enabled()

    result = get_organization_creation_eligibility(user)

    if not result.eligible:
        raise ValidationError({
            "code": result.code,
            "detail": result.detail,
        })

    return user.member_profile
