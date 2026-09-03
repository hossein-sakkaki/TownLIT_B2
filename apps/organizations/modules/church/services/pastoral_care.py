# apps/organizations/modules/church/services/pastoral_care.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchPastoralCareAssignmentRole,
    ChurchPastoralCareAssignmentStatus,
    ChurchPastoralCareCaseStatus,
    ChurchPastoralCareCategory,
    ChurchPastoralCareNoteType,
    ChurchPastoralCareNoteVisibility,
    ChurchPastoralCareSensitivity,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import (
    ChurchPastoralCareAssignment,
    ChurchPastoralCareCase,
    ChurchPastoralCareContact,
    ChurchPastoralCareNote,
)
from apps.organizations.modules.church.services.audit import record_church_audit
from apps.organizations.modules.church.services.pastoral_crypto import encrypt_pastoral_text
from apps.organizations.modules.church.services.pastoral_access import (
    can_view_pastoral_note,
    ensure_pastoral_case_access,
    ensure_pastoral_manage_permission,
    get_active_pastoral_membership_for_user,
    user_has_direct_church_permission,
    user_is_active_pastoral_case_assignee,
)


def _active_membership_for_actor(*, workspace, actor):
    membership = get_active_pastoral_membership_for_user(workspace=workspace, user=actor)
    if not membership:
        raise PermissionDenied("An active official Organization membership is required for pastoral care actions.")
    return membership


@transaction.atomic
def create_pastoral_care_case(
    *,
    workspace,
    congregant,
    actor,
    title,
    category=ChurchPastoralCareCategory.GENERAL,
    sensitivity=ChurchPastoralCareSensitivity.STANDARD,
    summary="",
):
    ensure_pastoral_manage_permission(actor=actor, workspace=workspace, require_write=True)
    if congregant.workspace_id != workspace.id:
        raise ValidationError({"congregant": "Pastoral care congregant must belong to this Church workspace."})
    if not congregant.is_active:
        raise ValidationError({"congregant": "Inactive congregation records cannot receive a new active pastoral care case."})

    opened_by = _active_membership_for_actor(workspace=workspace, actor=actor)
    care_case = ChurchPastoralCareCase(
        workspace=workspace,
        congregant=congregant,
        category=category,
        sensitivity=sensitivity,
        title=(title or "").strip(),
        summary_encrypted=encrypt_pastoral_text(summary),
        opened_by_membership=opened_by,
    )
    if not care_case.title:
        raise ValidationError({"title": "Pastoral care case title is required."})
    care_case.full_clean()
    care_case.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.PASTORAL_CASE_CREATED,
        actor=actor,
        entity=care_case,
        metadata={
            "category": category,
            "sensitivity": sensitivity,
            # Never copy title/summary or note content into the general Church audit log.
        },
    )
    return care_case


@transaction.atomic
def assign_pastoral_care_case(
    *,
    care_case,
    membership,
    actor,
    role=ChurchPastoralCareAssignmentRole.SUPPORT,
):
    care_case = ChurchPastoralCareCase.objects.select_for_update().select_related("workspace__activation__organization").get(pk=care_case.pk)
    ensure_pastoral_manage_permission(actor=actor, workspace=care_case.workspace, require_write=True)

    if care_case.status == ChurchPastoralCareCaseStatus.CLOSED:
        raise ValidationError("Closed pastoral care cases cannot receive active assignments.")
    if membership.organization_id != care_case.workspace.activation.organization_id:
        raise ValidationError({"membership": "Pastoral care assignee must belong to the same Organization."})
    if membership.status not in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES:
        raise ValidationError({"membership": "Pastoral care assignee must have an active Organization membership."})

    existing = (
        ChurchPastoralCareAssignment.objects
        .select_for_update()
        .filter(
            case=care_case,
            membership=membership,
            status=ChurchPastoralCareAssignmentStatus.ACTIVE,
        )
        .first()
    )
    if existing:
        return existing

    assignment = ChurchPastoralCareAssignment(
        case=care_case,
        membership=membership,
        role=role,
    )
    assignment.full_clean()
    assignment.save()

    record_church_audit(
        workspace=care_case.workspace,
        event=ChurchAuditEvent.PASTORAL_CASE_ASSIGNED,
        actor=actor,
        entity=assignment,
        metadata={"role": role},
    )
    return assignment


@transaction.atomic
def end_pastoral_care_assignment(*, assignment, actor):
    assignment = (
        ChurchPastoralCareAssignment.objects
        .select_for_update()
        .select_related("case__workspace")
        .get(pk=assignment.pk)
    )
    ensure_pastoral_manage_permission(actor=actor, workspace=assignment.case.workspace, require_write=True)

    if assignment.status == ChurchPastoralCareAssignmentStatus.ENDED:
        return assignment

    assignment.status = ChurchPastoralCareAssignmentStatus.ENDED
    assignment.ended_at = timezone.now()
    assignment.full_clean()
    assignment.save()

    record_church_audit(
        workspace=assignment.case.workspace,
        event=ChurchAuditEvent.PASTORAL_CASE_UNASSIGNED,
        actor=actor,
        entity=assignment,
    )
    return assignment


@transaction.atomic
def add_pastoral_care_note(
    *,
    care_case,
    actor,
    body,
    note_type=ChurchPastoralCareNoteType.GENERAL,
    visibility=ChurchPastoralCareNoteVisibility.CASE_TEAM,
    amends_note=None,
):
    care_case = ChurchPastoralCareCase.objects.select_for_update().select_related("workspace").get(pk=care_case.pk)
    ensure_pastoral_case_access(actor=actor, care_case=care_case, require_write=True)

    author_membership = _active_membership_for_actor(workspace=care_case.workspace, actor=actor)

    if visibility == ChurchPastoralCareNoteVisibility.PASTORAL_LEADERS:
        if not (
            user_has_direct_church_permission(
                user=actor,
                workspace=care_case.workspace,
                permission_key=ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
            )
            or user_has_direct_church_permission(
                user=actor,
                workspace=care_case.workspace,
                permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
            )
        ):
            raise PermissionDenied("Pastoral-leader notes require confidential pastoral care permission.")
    elif not (
        user_is_active_pastoral_case_assignee(user=actor, care_case=care_case)
        or user_has_direct_church_permission(
            user=actor,
            workspace=care_case.workspace,
            permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
        )
    ):
        raise PermissionDenied("Case-team notes require an active care assignment or pastoral care management permission.")

    note = ChurchPastoralCareNote(
        case=care_case,
        author_membership=author_membership,
        note_type=note_type,
        visibility=visibility,
        body_encrypted=encrypt_pastoral_text(body),
        amends_note=amends_note,
    )
    note.full_clean()
    note.save()

    record_church_audit(
        workspace=care_case.workspace,
        event=ChurchAuditEvent.PASTORAL_NOTE_ADDED,
        actor=actor,
        entity=note,
        metadata={"note_type": note_type, "visibility": visibility},
    )
    return note


@transaction.atomic
def record_pastoral_care_contact(
    *,
    care_case,
    actor,
    contact_type,
    occurred_at=None,
    summary="",
    follow_up_required=False,
    follow_up_due_at=None,
):
    care_case = ChurchPastoralCareCase.objects.select_for_update().select_related("workspace").get(pk=care_case.pk)
    ensure_pastoral_case_access(actor=actor, care_case=care_case, require_write=True)

    actor_membership = _active_membership_for_actor(workspace=care_case.workspace, actor=actor)
    if not (
        user_is_active_pastoral_case_assignee(user=actor, care_case=care_case)
        or user_has_direct_church_permission(
            user=actor,
            workspace=care_case.workspace,
            permission_key=ChurchPermissionKey.MANAGE_PASTORAL_CARE,
        )
    ):
        raise PermissionDenied("Recording pastoral contact requires an active care assignment or management permission.")

    contact = ChurchPastoralCareContact(
        case=care_case,
        actor_membership=actor_membership,
        contact_type=contact_type,
        occurred_at=occurred_at or timezone.now(),
        summary_encrypted=encrypt_pastoral_text(summary),
        follow_up_required=bool(follow_up_required),
        follow_up_due_at=follow_up_due_at,
    )
    contact.full_clean()
    contact.save()

    record_church_audit(
        workspace=care_case.workspace,
        event=ChurchAuditEvent.PASTORAL_CONTACT_RECORDED,
        actor=actor,
        entity=contact,
        metadata={
            "contact_type": contact_type,
            "follow_up_required": bool(follow_up_required),
        },
    )
    return contact


@transaction.atomic
def put_pastoral_care_case_on_hold(*, care_case, actor):
    care_case = ChurchPastoralCareCase.objects.select_for_update().select_related("workspace").get(pk=care_case.pk)
    ensure_pastoral_manage_permission(actor=actor, workspace=care_case.workspace, require_write=True)
    if care_case.status == ChurchPastoralCareCaseStatus.CLOSED:
        raise ValidationError("Closed pastoral care cases cannot be placed on hold.")
    if care_case.status == ChurchPastoralCareCaseStatus.ON_HOLD:
        return care_case

    care_case.status = ChurchPastoralCareCaseStatus.ON_HOLD
    care_case.full_clean()
    care_case.save()
    record_church_audit(workspace=care_case.workspace, event=ChurchAuditEvent.PASTORAL_CASE_ON_HOLD, actor=actor, entity=care_case)
    return care_case


@transaction.atomic
def reopen_pastoral_care_case(*, care_case, actor):
    care_case = ChurchPastoralCareCase.objects.select_for_update().select_related("workspace").get(pk=care_case.pk)
    ensure_pastoral_manage_permission(actor=actor, workspace=care_case.workspace, require_write=True)
    if care_case.status == ChurchPastoralCareCaseStatus.OPEN:
        return care_case

    care_case.status = ChurchPastoralCareCaseStatus.OPEN
    care_case.closed_at = None
    care_case.closed_by_membership = None
    care_case.closure_summary_encrypted = ""
    care_case.full_clean()
    care_case.save()
    record_church_audit(workspace=care_case.workspace, event=ChurchAuditEvent.PASTORAL_CASE_REOPENED, actor=actor, entity=care_case)
    return care_case


@transaction.atomic
def close_pastoral_care_case(*, care_case, actor, closure_summary=""):
    care_case = ChurchPastoralCareCase.objects.select_for_update().select_related("workspace").get(pk=care_case.pk)
    ensure_pastoral_manage_permission(actor=actor, workspace=care_case.workspace, require_write=True)
    if care_case.status == ChurchPastoralCareCaseStatus.CLOSED:
        return care_case

    closing_membership = _active_membership_for_actor(workspace=care_case.workspace, actor=actor)
    care_case.status = ChurchPastoralCareCaseStatus.CLOSED
    care_case.closed_at = timezone.now()
    care_case.closed_by_membership = closing_membership
    care_case.closure_summary_encrypted = encrypt_pastoral_text(closure_summary)
    care_case.full_clean()
    care_case.save()

    # Close all active case-team assignments without deleting history.
    now = timezone.now()
    assignments = ChurchPastoralCareAssignment.objects.select_for_update().filter(
        case=care_case,
        status=ChurchPastoralCareAssignmentStatus.ACTIVE,
    )
    for assignment in assignments:
        assignment.status = ChurchPastoralCareAssignmentStatus.ENDED
        assignment.ended_at = now
        assignment.save(update_fields=["status", "ended_at", "active_slot", "updated_at"])

    record_church_audit(
        workspace=care_case.workspace,
        event=ChurchAuditEvent.PASTORAL_CASE_CLOSED,
        actor=actor,
        entity=care_case,
    )
    return care_case


def assert_pastoral_note_visible(*, note, actor):
    if not can_view_pastoral_note(user=actor, note=note):
        raise PermissionDenied("You do not have access to this pastoral care note.")
    return note


def get_pastoral_care_case_summary(*, care_case, actor):
    ensure_pastoral_case_access(actor=actor, care_case=care_case, require_write=False)
    from apps.organizations.modules.church.services.pastoral_crypto import decrypt_pastoral_text
    return decrypt_pastoral_text(care_case.summary_encrypted)


def get_pastoral_care_case_closure_summary(*, care_case, actor):
    ensure_pastoral_case_access(actor=actor, care_case=care_case, require_write=False)
    from apps.organizations.modules.church.services.pastoral_crypto import decrypt_pastoral_text
    return decrypt_pastoral_text(care_case.closure_summary_encrypted)


def get_pastoral_care_note_body(*, note, actor):
    assert_pastoral_note_visible(note=note, actor=actor)
    from apps.organizations.modules.church.services.pastoral_crypto import decrypt_pastoral_text
    return decrypt_pastoral_text(note.body_encrypted)


def get_pastoral_care_contact_summary(*, contact, actor):
    ensure_pastoral_case_access(actor=actor, care_case=contact.case, require_write=False)
    from apps.organizations.modules.church.services.pastoral_crypto import decrypt_pastoral_text
    return decrypt_pastoral_text(contact.summary_encrypted)
