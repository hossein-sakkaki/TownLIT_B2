# apps/organizations/feature_flags.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.conf import settings
from django.core.exceptions import ValidationError


def organizations_enabled() -> bool:
    return bool(
        getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_ENABLED",
            False,
        )
    )


def organization_creation_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_CREATION_ENABLED",
            False,
        )
    )


def organization_verification_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_VERIFICATION_ENABLED",
            False,
        )
    )


def organization_hierarchy_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_HIERARCHY_ENABLED",
            False,
        )
    )


def organization_modules_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_MODULES_ENABLED",
            False,
        )
    )


def organization_governance_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_GOVERNANCE_ENABLED",
            False,
        )
    )


def organization_ios_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_IOS_ENABLED",
            False,
        )
    )


def organization_android_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_ANDROID_ENABLED",
            False,
        )
    )


def organization_web_admin_enabled() -> bool:
    return bool(
        organizations_enabled()
        and getattr(
            settings,
            "TOWNLIT_ORGANIZATIONS_WEB_ADMIN_ENABLED",
            False,
        )
    )


def ensure_organizations_enabled():
    if not organizations_enabled():
        raise ValidationError(
            "Organizations are currently unavailable."
        )


def ensure_organization_creation_enabled():
    ensure_organizations_enabled()

    if not organization_creation_enabled():
        raise ValidationError(
            "Organization creation is currently unavailable."
        )


def ensure_organization_verification_enabled():
    ensure_organizations_enabled()

    if not organization_verification_enabled():
        raise ValidationError(
            "Organization verification is currently unavailable."
        )


def ensure_organization_hierarchy_enabled():
    ensure_organizations_enabled()

    if not organization_hierarchy_enabled():
        raise ValidationError(
            "Organization hierarchy is currently unavailable."
        )


def ensure_organization_governance_enabled():
    ensure_organizations_enabled()

    if not organization_governance_enabled():
        raise ValidationError(
            "Organization governance is currently unavailable."
        )


def ensure_organization_modules_enabled():
    ensure_organizations_enabled()

    if not organization_modules_enabled():
        raise ValidationError(
            "Organization modules are currently unavailable."
        )
