# apps/organization_content/services/access.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from django.core.exceptions import PermissionDenied, ValidationError

from apps.organizations.constants import (
    OrganizationPermissionKey, OrganizationStatus, OrganizationVisibility,
)
from apps.organizations.services.access import user_has_organization_permission


def organization_has_profile_content_feed(organization):
    return (
        organization.status == OrganizationStatus.ACTIVE
        and organization.visibility in {
            OrganizationVisibility.PUBLIC, OrganizationVisibility.UNLISTED,
        }
    )


def can_view_organization_content(*, organization, viewer=None):
    if not organization_has_profile_content_feed(organization):
        return False
    # Unlisted profiles are reachable directly by signed-in users, not listed
    # in discovery. Preserve anonymous access to existing public feeds only.
    return (
        organization.visibility == OrganizationVisibility.PUBLIC
        or bool(getattr(viewer, "is_authenticated", False))
    )


def can_manage_content(*, actor, organization):
    if organization.status != "active":
        return False
    return any(
        user_has_organization_permission(
            user=actor, organization=organization, permission_key=key,
        )
        for key in (
            OrganizationPermissionKey.MANAGE_CONTENT,
            OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS,
        )
    )


def ensure_content_manager(*, actor, organization):
    if not can_manage_content(actor=actor, organization=organization):
        raise PermissionDenied("You do not have permission to manage Organization content.")


def ensure_update_editable(update):
    from apps.sanctuary.services.held_content_access import is_under_active_safety_hold

    if update.status == update.Status.ARCHIVED:
        raise ValidationError("Archived Organization content cannot be edited.")
    if not update.is_active or update.is_suspended or is_under_active_safety_hold(update):
        raise ValidationError("This Organization content is unavailable or under review.")


def ensure_update_revision(*, update, expected_updated_at=None):
    if expected_updated_at is not None and update.updated_at != expected_updated_at:
        raise ValidationError({
            "expected_updated_at": "This content changed. Reopen the latest draft before saving or publishing.",
        })


def is_organization_update_type(content_type):
    return bool(
        content_type
        and content_type.app_label == "organization_content"
        and content_type.model == "organizationupdate"
    )


def ensure_update_interaction_access(*, content_type, object_id):
    """Interactions are public-post actions, including for managers."""
    if not is_organization_update_type(content_type):
        return
    from apps.organization_content.models import OrganizationUpdate

    try:
        update = OrganizationUpdate.objects.select_related("organization").get(pk=object_id)
    except (OrganizationUpdate.DoesNotExist, ValueError, TypeError):
        raise PermissionDenied("This Organization content is not available.")
    if not update.is_publicly_available:
        raise PermissionDenied("This Organization content is not available.")
