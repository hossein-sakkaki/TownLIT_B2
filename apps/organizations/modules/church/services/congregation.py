# apps/organizations/modules/church/services/congregation.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants.user_labels import YOUNG_PATH
from apps.core.owner_visibility.policy import OwnerVisibilityPolicy
from apps.organizations.constants import ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchCongregantSource,
    ChurchCongregantStatus,
    ChurchDirectoryVisibility,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import ChurchCongregant
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


def _display_name_for_user(user) -> str:
    parts = [
        (getattr(user, "name", "") or "").strip(),
        (getattr(user, "family", "") or "").strip(),
    ]
    full_name = " ".join(part for part in parts if part).strip()
    return full_name or (getattr(user, "username", "") or "").strip() or "TownLIT User"


def _ensure_supported_profile_user(user):
    if not user:
        raise ValidationError("A valid TownLIT account is required.")

    if getattr(user, "is_deleted", False):
        raise ValidationError("Deleted accounts cannot be registered as active Church congregants.")
    if getattr(user, "is_suspended", False):
        raise ValidationError("Suspended accounts cannot be registered as active Church congregants.")
    if getattr(user, "is_account_paused", False):
        raise ValidationError("Paused accounts cannot be registered as active Church congregants.")

    label = getattr(user, "label", None)
    if label and getattr(label, "name", None) == YOUNG_PATH:
        raise ValidationError(
            "Protected child/youth account integration is not available in Church Congregation V1."
        )


def _resolve_current_official_membership(*, workspace, member):
    return (
        workspace.activation.organization.memberships
        .filter(
            member=member,
            status__in=ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES,
        )
        .order_by("-joined_at", "-id")
        .first()
    )


@transaction.atomic
def register_member_congregant(
    *,
    workspace,
    member,
    actor,
    campus=None,
    status=ChurchCongregantStatus.REGULAR,
    source=ChurchCongregantSource.STAFF_CREATED,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    )

    member = member.__class__.objects.select_related("user", "user__label").get(pk=member.pk)
    _ensure_supported_profile_user(member.user)

    if campus and campus.workspace_id != workspace.id:
        raise ValidationError({"campus": "Congregant campus must belong to this Church workspace."})

    official_membership = _resolve_current_official_membership(
        workspace=workspace,
        member=member,
    )

    congregant = (
        ChurchCongregant.objects
        .select_for_update()
        .filter(workspace=workspace, member=member)
        .first()
    )

    display_name = _display_name_for_user(member.user)

    if congregant:
        congregant.display_name_snapshot = display_name
        congregant.official_membership = official_membership
        congregant.campus = campus if campus is not None else congregant.campus
        congregant.status = status
        congregant.is_active = True
        congregant.updated_by = actor
        congregant.full_clean()
        congregant.save()
        event = ChurchAuditEvent.CONGREGANT_UPDATED
    else:
        congregant = ChurchCongregant(
            workspace=workspace,
            member=member,
            official_membership=official_membership,
            display_name_snapshot=display_name,
            status=status,
            source=source,
            campus=campus,
            created_by=actor,
            updated_by=actor,
        )
        congregant.full_clean()
        congregant.save()
        event = ChurchAuditEvent.CONGREGANT_REGISTERED

    record_church_audit(
        workspace=workspace,
        event=event,
        actor=actor,
        entity=congregant,
        metadata={
            "identity_kind": "member",
            "official_membership_current": bool(official_membership),
        },
    )

    return congregant


@transaction.atomic
def register_guest_congregant(
    *,
    workspace,
    guest_profile,
    actor,
    campus=None,
    status=ChurchCongregantStatus.NEWCOMER,
    source=ChurchCongregantSource.STAFF_CREATED,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    )

    guest_profile = guest_profile.__class__.objects.select_related("user", "user__label").get(pk=guest_profile.pk)
    if not guest_profile.is_active:
        raise ValidationError("Inactive Guest profiles cannot be registered as active Church congregants.")
    _ensure_supported_profile_user(guest_profile.user)

    if campus and campus.workspace_id != workspace.id:
        raise ValidationError({"campus": "Congregant campus must belong to this Church workspace."})

    if status == ChurchCongregantStatus.REGULAR:
        # Guest accounts are intentionally kept on the limited attendee path.
        status = ChurchCongregantStatus.ATTENDEE

    congregant = (
        ChurchCongregant.objects
        .select_for_update()
        .filter(workspace=workspace, guest_profile=guest_profile)
        .first()
    )

    display_name = _display_name_for_user(guest_profile.user)

    if congregant:
        congregant.display_name_snapshot = display_name
        congregant.campus = campus if campus is not None else congregant.campus
        congregant.status = status
        congregant.directory_visibility = ChurchDirectoryVisibility.STAFF_ONLY
        congregant.directory_consent_at = None
        congregant.is_active = True
        congregant.updated_by = actor
        congregant.full_clean()
        congregant.save()
        event = ChurchAuditEvent.CONGREGANT_UPDATED
    else:
        congregant = ChurchCongregant(
            workspace=workspace,
            guest_profile=guest_profile,
            display_name_snapshot=display_name,
            status=status,
            source=source,
            campus=campus,
            directory_visibility=ChurchDirectoryVisibility.STAFF_ONLY,
            created_by=actor,
            updated_by=actor,
        )
        congregant.full_clean()
        congregant.save()
        event = ChurchAuditEvent.CONGREGANT_REGISTERED

    record_church_audit(
        workspace=workspace,
        event=event,
        actor=actor,
        entity=congregant,
        metadata={"identity_kind": "guest"},
    )

    return congregant


@transaction.atomic
def register_external_congregant(
    *,
    workspace,
    display_name,
    actor,
    campus=None,
    status=ChurchCongregantStatus.NEWCOMER,
    source=ChurchCongregantSource.STAFF_CREATED,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    )

    display_name = (display_name or "").strip()
    if not display_name:
        raise ValidationError({"display_name": "Display name is required."})
    if campus and campus.workspace_id != workspace.id:
        raise ValidationError({"campus": "Congregant campus must belong to this Church workspace."})

    congregant = ChurchCongregant(
        workspace=workspace,
        display_name_snapshot=display_name,
        status=status,
        source=source,
        campus=campus,
        directory_visibility=ChurchDirectoryVisibility.STAFF_ONLY,
        created_by=actor,
        updated_by=actor,
    )
    congregant.full_clean()
    congregant.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.CONGREGANT_REGISTERED,
        actor=actor,
        entity=congregant,
        metadata={"identity_kind": "external"},
    )

    return congregant


@transaction.atomic
def update_church_congregant(
    *,
    congregant,
    actor,
    campus=None,
    status=None,
    preferred_name=None,
    is_active=None,
    last_seen_at=None,
):
    congregant = ChurchCongregant.objects.select_for_update().select_related("workspace", "campus").get(pk=congregant.pk)

    ensure_church_permission(
        actor=actor,
        workspace=congregant.workspace,
        permission_key=ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    )

    if campus is not None:
        if campus.workspace_id != congregant.workspace_id:
            raise ValidationError({"campus": "Congregant campus must belong to this Church workspace."})
        congregant.campus = campus
    if status is not None:
        congregant.status = status
    if preferred_name is not None:
        congregant.preferred_name = (preferred_name or "").strip()
    if is_active is not None:
        congregant.is_active = bool(is_active)
    if last_seen_at is not None:
        congregant.last_seen_at = last_seen_at

    congregant.updated_by = actor
    congregant.full_clean()
    congregant.save()

    record_church_audit(
        workspace=congregant.workspace,
        event=ChurchAuditEvent.CONGREGANT_UPDATED,
        actor=actor,
        entity=congregant,
    )

    return congregant


@transaction.atomic
def sync_member_congregant_official_membership(*, congregant, actor):
    congregant = ChurchCongregant.objects.select_for_update().select_related("workspace", "member__user").get(pk=congregant.pk)

    ensure_church_permission(
        actor=actor,
        workspace=congregant.workspace,
        permission_key=ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
    )

    if not congregant.member_id:
        raise ValidationError("Only Member-backed congregants can synchronize official membership.")

    congregant.official_membership = _resolve_current_official_membership(
        workspace=congregant.workspace,
        member=congregant.member,
    )
    if (
        congregant.directory_visibility == ChurchDirectoryVisibility.ORGANIZATION_MEMBERS
        and not congregant.official_membership_id
    ):
        congregant.directory_visibility = ChurchDirectoryVisibility.STAFF_ONLY
        congregant.directory_consent_at = None
    congregant.display_name_snapshot = _display_name_for_user(congregant.member.user)
    congregant.updated_by = actor
    congregant.full_clean()
    congregant.save()

    record_church_audit(
        workspace=congregant.workspace,
        event=ChurchAuditEvent.CONGREGANT_UPDATED,
        actor=actor,
        entity=congregant,
        metadata={"official_membership_synchronized": True},
    )

    return congregant


@transaction.atomic
def set_own_church_directory_visibility(*, congregant, actor, visibility):
    congregant = ChurchCongregant.objects.select_for_update().select_related("member__user", "workspace__activation__organization").get(pk=congregant.pk)

    # Read/write module gate still applies to self-service state changes.
    from apps.organizations.modules.church.services.access import ensure_church_module_access
    ensure_church_module_access(workspace=congregant.workspace, require_write=True)

    if not congregant.member_id or congregant.member.user_id != getattr(actor, "id", None):
        raise PermissionDenied("Only the Member represented by this congregation record can change member-directory visibility.")

    if visibility not in {
        ChurchDirectoryVisibility.STAFF_ONLY,
        ChurchDirectoryVisibility.ORGANIZATION_MEMBERS,
    }:
        raise ValidationError({"visibility": "Unsupported Church directory visibility."})

    if visibility == ChurchDirectoryVisibility.ORGANIZATION_MEMBERS:
        official_membership = _resolve_current_official_membership(
            workspace=congregant.workspace,
            member=congregant.member,
        )
        if not official_membership:
            raise ValidationError(
                "Only active official Organization members can opt into the organization member directory."
            )
        if not OwnerVisibilityPolicy.is_publicly_discoverable(congregant.member.user, congregant.member):
            raise ValidationError(
                "Private, suspended, paused, deleted, inactive, or safety-hidden Member profiles cannot opt into the organization member directory."
            )
        congregant.official_membership = official_membership
        congregant.directory_consent_at = timezone.now()
    else:
        congregant.directory_consent_at = None

    congregant.directory_visibility = visibility
    congregant.updated_by = actor
    congregant.full_clean()
    congregant.save()

    record_church_audit(
        workspace=congregant.workspace,
        event=ChurchAuditEvent.CONGREGANT_DIRECTORY_VISIBILITY_CHANGED,
        actor=actor,
        entity=congregant,
        metadata={"directory_visibility": visibility},
    )

    return congregant
