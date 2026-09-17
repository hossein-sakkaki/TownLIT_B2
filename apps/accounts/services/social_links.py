# apps/accounts/services/social_links.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from apps.organizations.constants import OrganizationPermissionKey
from apps.organizations.feature_flags import organizations_enabled
from apps.organizations.models import Organization
from apps.organizations.services.access import (
    user_has_organization_permission,
)


CustomUser = get_user_model()

SOCIAL_OWNER_USER = "customuser"
SOCIAL_OWNER_ORGANIZATION = "organization"


def social_content_type_for_key(content_type_key):
    if content_type_key == SOCIAL_OWNER_USER:
        return ContentType.objects.get_for_model(
            CustomUser
        )

    if content_type_key == SOCIAL_OWNER_ORGANIZATION:
        return ContentType.objects.get_for_model(
            Organization
        )

    return None


def resolve_social_owner_for_management(
    *,
    actor,
    content_type_key,
    object_id,
):
    try:
        object_id = int(object_id)
    except (TypeError, ValueError):
        return None

    if object_id <= 0:
        return None

    if content_type_key == SOCIAL_OWNER_USER:
        if object_id != actor.id:
            return None

        return actor

    if content_type_key != SOCIAL_OWNER_ORGANIZATION:
        return None

    if not organizations_enabled():
        return None

    organization = (
        Organization.objects
        .filter(pk=object_id)
        .first()
    )

    if organization is None:
        return None

    if not user_has_organization_permission(
        user=actor,
        organization=organization,
        permission_key=(
            OrganizationPermissionKey.MANAGE_PROFILE
        ),
    ):
        return None

    return organization