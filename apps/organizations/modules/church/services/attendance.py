# apps/organizations/modules/church/services/attendance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAttendancePresence,
    ChurchAttendanceSessionStatus,
    ChurchAttendanceSource,
    ChurchAuditEvent,
    ChurchGatheringOccurrenceStatus,
    ChurchPermissionKey,
)
from apps.organizations.modules.church.models import (
    ChurchAttendanceRecord,
    ChurchAttendanceSession,
    ChurchGatheringOccurrence,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


@transaction.atomic
def open_church_attendance_session(*, occurrence, actor, now=None):
    now = now or timezone.now()
    occurrence = (
        ChurchGatheringOccurrence.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=occurrence.pk)
    )
    workspace = occurrence.workspace

    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_ATTENDANCE,
    )

    if not workspace.attendance_tracking_enabled:
        raise ValidationError(
            "Attendance tracking is disabled for this Church workspace."
        )

    if occurrence.status == ChurchGatheringOccurrenceStatus.CANCELED:
        raise ValidationError(
            "Attendance cannot be opened for a canceled gathering."
        )

    session = ChurchAttendanceSession.objects.filter(
        occurrence=occurrence,
    ).first()

    if session:
        return session

    session = ChurchAttendanceSession(
        workspace=workspace,
        occurrence=occurrence,
        opened_at=now,
        opened_by=actor,
    )
    session.full_clean()
    session.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.ATTENDANCE_OPENED,
        actor=actor,
        entity=session,
        metadata={
            "occurrence_public_id": str(occurrence.public_id),
        },
    )

    return session


@transaction.atomic
def check_in_church_member(
    *,
    session,
    membership,
    actor,
    presence=ChurchAttendancePresence.PRESENT,
    source=ChurchAttendanceSource.MANUAL,
    now=None,
):
    now = now or timezone.now()
    session = (
        ChurchAttendanceSession.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=session.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=session.workspace,
        permission_key=ChurchPermissionKey.MANAGE_ATTENDANCE,
    )

    if session.status != ChurchAttendanceSessionStatus.OPEN:
        raise ValidationError("Attendance session is closed.")

    if membership.status != OrganizationMembershipStatus.ACTIVE:
        raise ValidationError(
            "Only active organization members can be checked in."
        )

    record = ChurchAttendanceRecord.objects.filter(
        session=session,
        membership=membership,
    ).first()

    if record:
        return record

    record = ChurchAttendanceRecord(
        session=session,
        membership=membership,
        presence=presence,
        source=source,
        checked_in_at=now,
        recorded_by=actor,
    )
    record.full_clean()
    record.save()

    record_church_audit(
        workspace=session.workspace,
        event=ChurchAuditEvent.ATTENDANCE_CHECKED_IN,
        actor=actor,
        membership=membership,
        entity=record,
        metadata={
            "session_public_id": str(session.public_id),
            "presence": record.presence,
            "source": record.source,
        },
    )

    return record


@transaction.atomic
def check_out_church_member(*, record, actor, now=None):
    now = now or timezone.now()
    record = (
        ChurchAttendanceRecord.objects
        .select_for_update()
        .select_related(
            "session__workspace__activation__organization",
            "membership",
        )
        .get(pk=record.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=record.session.workspace,
        permission_key=ChurchPermissionKey.MANAGE_ATTENDANCE,
    )

    if record.checked_out_at:
        return record

    if now <= record.checked_in_at:
        raise ValidationError("Checkout must occur after check-in.")

    record.checked_out_at = now
    record.full_clean()
    record.save(update_fields=["checked_out_at", "updated_at"])

    record_church_audit(
        workspace=record.session.workspace,
        event=ChurchAuditEvent.ATTENDANCE_CHECKED_OUT,
        actor=actor,
        membership=record.membership,
        entity=record,
    )

    return record


@transaction.atomic
def update_church_guest_counts(
    *,
    session,
    actor,
    unregistered_adult_count,
    unregistered_child_count,
    anonymous_online_count=0,
):
    session = (
        ChurchAttendanceSession.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=session.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=session.workspace,
        permission_key=ChurchPermissionKey.MANAGE_ATTENDANCE,
    )

    if session.status != ChurchAttendanceSessionStatus.OPEN:
        raise ValidationError("Attendance session is closed.")

    counts = {
        "unregistered_adult_count": unregistered_adult_count,
        "unregistered_child_count": unregistered_child_count,
        "anonymous_online_count": anonymous_online_count,
    }

    if any(int(value) < 0 for value in counts.values()):
        raise ValidationError("Attendance guest counts cannot be negative.")

    for field, value in counts.items():
        setattr(session, field, int(value))

    session.save(
        update_fields=[
            *counts.keys(),
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=session.workspace,
        event=ChurchAuditEvent.ATTENDANCE_GUEST_COUNTS_UPDATED,
        actor=actor,
        entity=session,
        metadata=counts,
    )

    return session


@transaction.atomic
def close_church_attendance_session(*, session, actor, now=None):
    now = now or timezone.now()
    session = (
        ChurchAttendanceSession.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=session.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=session.workspace,
        permission_key=ChurchPermissionKey.MANAGE_ATTENDANCE,
    )

    if session.status == ChurchAttendanceSessionStatus.CLOSED:
        return session

    session.status = ChurchAttendanceSessionStatus.CLOSED
    session.closed_at = now
    session.closed_by = actor
    session.full_clean()
    session.save(
        update_fields=[
            "status",
            "closed_at",
            "closed_by",
            "updated_at",
        ]
    )

    record_church_audit(
        workspace=session.workspace,
        event=ChurchAuditEvent.ATTENDANCE_CLOSED,
        actor=actor,
        entity=session,
        metadata={
            "registered_attendee_count": session.registered_attendee_count,
            "aggregate_guest_count": session.aggregate_guest_count,
            "total_attendance_count": session.total_attendance_count,
        },
    )

    return session
