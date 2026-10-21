# apps/posts/services/organization_comment_identity.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q

from apps.organizations.constants import (
    ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    OrganizationPermissionKey, OrganizationRoleKey, OrganizationRoleScope,
)
from apps.organizations.models import OrganizationMembership
from apps.organizations.services.access import user_has_organization_permission_strict
from apps.organization_content.services.access import (
    ensure_update_interaction_access, is_organization_update_type,
)


def can_reply_as_organization(*, user, organization):
    return (
        organization.status == "active"
        and user_has_organization_permission_strict(
            user=user,
            organization=organization,
            permission_key=OrganizationPermissionKey.REPLY_COMMENTS,
        )
    )


def validate_comment_organization(*, user, organization_id, content_type, object_id):
    """Only own, publicly accessible Organization Updates may receive official replies."""
    if not is_organization_update_type(content_type):
        raise PermissionDenied("Organization identity is not available for this content.")

    ensure_update_interaction_access(content_type=content_type, object_id=object_id)
    from apps.organization_content.models import OrganizationUpdate
    update = OrganizationUpdate.objects.select_related("organization").get(pk=object_id)

    if str(update.organization_id) != str(organization_id):
        raise PermissionDenied("This content belongs to another Organization.")

    organization = update.organization
    if not can_reply_as_organization(user=user, organization=organization):
        raise PermissionDenied("You cannot comment on behalf of this Organization.")
    return organization


def can_inspect_comment_operator(*, user, comment):
    org = comment.acting_organization
    if not org or not getattr(user, "is_authenticated", False):
        return False
    if comment.name_id == user.pk:
        return True

    # An active organization-scoped Owner or Administrator, not generic staff.
    now = timezone.now()
    return OrganizationMembership.objects.filter(
        organization_id=org.pk,
        member__user=user,
        status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        role_assignments__is_active=True,
        role_assignments__revoked_at__isnull=True,
        role_assignments__starts_at__lte=now,
        role_assignments__role__is_active=True,
        role_assignments__role__key__in=(
            OrganizationRoleKey.OWNER, OrganizationRoleKey.ADMINISTRATOR,
        ),
        role_assignments__scope_type=OrganizationRoleScope.ORGANIZATION,
        role_assignments__scope_key="",
    ).filter(
        Q(role_assignments__ends_at__isnull=True)
        | Q(role_assignments__ends_at__gt=now)
    ).exists()


def public_organization_identity(organization, request=None):
    from apps.organizations.serializers.organization import (
        _organization_logo_url,
    )
    from apps.organizations.selectors.verification import (
        is_organization_verified,
    )

    return {
        "id": organization.pk,
        "name": organization.name,
        "slug": organization.slug,
        "logo_url": _organization_logo_url(
            organization,
            request=request,
        ),
        "is_verified": is_organization_verified(
            organization=organization,
        ),
        "brand_color": (
            str(getattr(organization, "brand_color", "") or "").strip()
            or None
        ),
    }


def legacy_public_name(organization, request=None):
    """Compatible shape for older clients, never the underlying human actor."""
    identity = public_organization_identity(organization, request=request)
    return {
        "id": -organization.pk,
        "username": f"org__{organization.slug}",
        "name": organization.name,
        "family": "",
        "avatar_url": identity["logo_url"],
        "avatar_cdn_url": None,
        "avatar_version": None,
        "profile_image": identity["logo_url"],
        "is_verified_identity": False,
        "is_townlit_verified": False,
        "label_color": None,
        "label": None,
    }
