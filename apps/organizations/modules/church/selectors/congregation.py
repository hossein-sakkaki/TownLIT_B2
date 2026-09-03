# apps/organizations/modules/church/selectors/congregation.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from apps.organizations.constants import ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
from apps.organizations.modules.church.constants import ChurchDirectoryVisibility
from apps.organizations.modules.church.models import ChurchCongregant
from apps.organizations.modules.church.services.access import user_has_church_permission
from apps.organizations.modules.church.constants import ChurchPermissionKey


def get_church_congregant_display_name(congregant) -> str:
    if congregant.preferred_name:
        return congregant.preferred_name

    if congregant.member_id:
        member = congregant.member
        user = member.user
        if (
            not user.is_deleted
            and not user.is_suspended
            and not user.is_account_paused
            and member.is_active
            and not member.is_hidden_by_confidants
        ):
            parts = [
                (user.name or "").strip(),
                (user.family or "").strip(),
            ]
            full_name = " ".join(part for part in parts if part).strip()
            return full_name or user.username
        return "Profile unavailable"

    if congregant.guest_profile_id:
        guest = congregant.guest_profile
        user = guest.user
        if (
            guest.is_active
            and not user.is_deleted
            and not user.is_suspended
            and not user.is_account_paused
        ):
            parts = [
                (user.name or "").strip(),
                (user.family or "").strip(),
            ]
            full_name = " ".join(part for part in parts if part).strip()
            return full_name or user.username
        return "Profile unavailable"

    return congregant.display_name_snapshot


def list_internal_church_congregants(*, workspace, actor):
    if not user_has_church_permission(
        user=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
    ):
        return ChurchCongregant.objects.none()

    return (
        ChurchCongregant.objects
        .select_related(
            "member__user",
            "guest_profile__user",
            "official_membership",
            "campus",
        )
        .filter(workspace=workspace, is_active=True)
        .order_by("display_name_snapshot", "id")
    )


def list_member_visible_church_congregants(*, workspace, viewer):
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return ChurchCongregant.objects.none()

    organization = workspace.activation.organization
    if not organization.memberships.filter(
        member__user=viewer,
        status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
    ).exists():
        return ChurchCongregant.objects.none()

    # Guest/external records are intentionally excluded from the member directory in V1.
    return (
        ChurchCongregant.objects
        .select_related("member__user", "official_membership", "campus")
        .filter(
            workspace=workspace,
            is_active=True,
            member__isnull=False,
            directory_visibility=ChurchDirectoryVisibility.ORGANIZATION_MEMBERS,
            directory_consent_at__isnull=False,
            member__is_active=True,
            member__is_privacy=False,
            member__is_hidden_by_confidants=False,
            member__user__is_deleted=False,
            member__user__is_suspended=False,
            member__user__is_account_paused=False,
            official_membership__status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        )
        .order_by("display_name_snapshot", "id")
    )
