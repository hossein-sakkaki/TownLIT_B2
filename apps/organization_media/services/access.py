# apps/organization_media/services/access.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from apps.organization_content.services.access import can_manage_content
from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.services.access import user_has_organization_permission


def can_manage_media(*, actor, organization):
    return can_manage_content(actor=actor, organization=organization) or (
        organization.status == "active"
        and user_has_organization_permission(
            user=actor, organization=organization,
            permission_key=OrganizationPermissionKey.MANAGE_PROFILE,
        )
    )


def can_deliver_organization_asset(*, asset, viewer):
    if not asset.is_ready_for_publication():
        return False

    from apps.sanctuary.services.held_content_access import (
        is_sanctuary_review_admin, is_under_active_safety_hold,
    )

    updates = [usage.update for usage in asset.update_usages.select_related(
        "update__organization"
    )]
    if any(is_under_active_safety_hold(update) for update in updates):
        return is_sanctuary_review_admin(viewer)
    if can_manage_media(actor=viewer, organization=asset.organization):
        return True
    if any(update.content_visibility_allowed(viewer=viewer) for update in updates):
        return True
    organization = asset.organization
    return bool(
        organization.status == "active"
        and organization.visibility == "public"
        and organization.intro_video_id == asset.pk
    )
