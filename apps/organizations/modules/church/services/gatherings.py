# apps/organizations/modules/church/services/gatherings.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.modules.church.constants import (
    ChurchAuditEvent,
    ChurchGatheringOccurrenceSource,
    ChurchGatheringOccurrenceStatus,
    ChurchGatheringSeriesStatus,
    ChurchMonthlyWeek,
    ChurchPermissionKey,
    ChurchRecurrenceFrequency,
)
from apps.organizations.modules.church.models import (
    ChurchGatheringOccurrence,
    ChurchGatheringSeries,
)
from apps.organizations.modules.church.services.access import ensure_church_permission
from apps.organizations.modules.church.services.audit import record_church_audit


_MAX_MATERIALIZATION_DAYS = 730


def _is_monthly_match(day, *, weekday, monthly_week):
    if day.weekday() != weekday:
        return False

    if monthly_week == ChurchMonthlyWeek.LAST:
        return (day + timedelta(days=7)).month != day.month

    occurrence_index = ((day.day - 1) // 7) + 1
    expected = {
        ChurchMonthlyWeek.FIRST: 1,
        ChurchMonthlyWeek.SECOND: 2,
        ChurchMonthlyWeek.THIRD: 3,
        ChurchMonthlyWeek.FOURTH: 4,
    }[monthly_week]
    return occurrence_index == expected


def _series_matches_date(series, day):
    if day < series.effective_start_date:
        return False

    if series.effective_end_date and day > series.effective_end_date:
        return False

    if day.weekday() != series.weekday:
        return False

    if series.recurrence_frequency == ChurchRecurrenceFrequency.WEEKLY:
        return True

    if series.recurrence_frequency == ChurchRecurrenceFrequency.BIWEEKLY:
        delta_days = (day - series.effective_start_date).days
        return (delta_days // 7) % 2 == 0

    if series.recurrence_frequency == ChurchRecurrenceFrequency.MONTHLY:
        return _is_monthly_match(
            day,
            weekday=series.weekday,
            monthly_week=series.monthly_week,
        )

    return False


def _occurrence_window(series, day):
    tz = ZoneInfo(
        series.campus.effective_timezone
        if series.campus_id
        else series.workspace.effective_timezone
    )
    starts_at = datetime.combine(
        day,
        series.local_start_time,
        tzinfo=tz,
    )
    ends_at = starts_at + timedelta(minutes=series.duration_minutes)
    return starts_at, ends_at


@transaction.atomic
def create_church_gathering_series(
    *,
    workspace,
    actor,
    name,
    gathering_type,
    recurrence_frequency,
    weekday,
    local_start_time,
    effective_start_date,
    campus=None,
    ministry=None,
    monthly_week=None,
    duration_minutes=None,
    effective_end_date=None,
    description=None,
    location_label=None,
    visibility="public",
    auto_create_attendance=False,
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
    )

    series = ChurchGatheringSeries(
        workspace=workspace,
        campus=campus,
        ministry=ministry,
        name=name,
        gathering_type=gathering_type,
        recurrence_frequency=recurrence_frequency,
        weekday=weekday,
        monthly_week=monthly_week,
        local_start_time=local_start_time,
        duration_minutes=(
            duration_minutes
            or workspace.default_gathering_duration_minutes
        ),
        effective_start_date=effective_start_date,
        effective_end_date=effective_end_date,
        description=description,
        location_label=location_label,
        visibility=visibility,
        auto_create_attendance=auto_create_attendance,
    )
    series.full_clean()
    series.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.GATHERING_SERIES_CREATED,
        actor=actor,
        entity=series,
        metadata={
            "gathering_type": series.gathering_type,
            "recurrence_frequency": series.recurrence_frequency,
        },
    )

    return series


@transaction.atomic
def update_church_gathering_series(*, series, actor, **changes):
    series = (
        ChurchGatheringSeries.objects
        .select_for_update()
        .select_related(
            "workspace__activation__organization",
            "campus",
            "ministry",
        )
        .get(pk=series.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=series.workspace,
        permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
    )

    allowed_fields = {
        "name",
        "gathering_type",
        "description",
        "location_label",
        "visibility",
        "status",
        "recurrence_frequency",
        "weekday",
        "monthly_week",
        "local_start_time",
        "duration_minutes",
        "effective_start_date",
        "effective_end_date",
        "auto_create_attendance",
        "campus",
        "ministry",
    }

    unknown = set(changes) - allowed_fields
    if unknown:
        raise ValidationError(
            f"Unsupported gathering series fields: {sorted(unknown)}"
        )

    for field, value in changes.items():
        setattr(series, field, value)

    series.full_clean()
    series.save()

    record_church_audit(
        workspace=series.workspace,
        event=ChurchAuditEvent.GATHERING_SERIES_UPDATED,
        actor=actor,
        entity=series,
    )

    return series


@transaction.atomic
def create_church_gathering_occurrence(
    *,
    workspace,
    actor,
    title,
    gathering_type,
    starts_at,
    ends_at,
    campus=None,
    ministry=None,
    location_label=None,
    visibility="public",
):
    ensure_church_permission(
        actor=actor,
        workspace=workspace,
        permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
    )

    occurrence = ChurchGatheringOccurrence(
        workspace=workspace,
        campus=campus,
        ministry=ministry,
        title=title,
        gathering_type=gathering_type,
        starts_at=starts_at,
        ends_at=ends_at,
        location_label=location_label,
        visibility=visibility,
        source=ChurchGatheringOccurrenceSource.MANUAL,
        created_by=actor,
    )
    occurrence.full_clean()
    occurrence.save()

    record_church_audit(
        workspace=workspace,
        event=ChurchAuditEvent.GATHERING_CREATED,
        actor=actor,
        entity=occurrence,
        metadata={"source": occurrence.source},
    )

    return occurrence


@transaction.atomic
def materialize_church_gathering_occurrences(
    *,
    series,
    actor,
    from_date,
    through_date,
):
    if not isinstance(from_date, date) or not isinstance(through_date, date):
        raise ValidationError("Materialization bounds must be dates.")

    if through_date < from_date:
        raise ValidationError("Materialization end date must not precede start date.")

    if (through_date - from_date).days > _MAX_MATERIALIZATION_DAYS:
        raise ValidationError(
            f"Materialization windows cannot exceed {_MAX_MATERIALIZATION_DAYS} days."
        )

    series = (
        ChurchGatheringSeries.objects
        .select_for_update()
        .select_related(
            "workspace__activation__organization",
            "campus",
            "ministry",
        )
        .get(pk=series.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=series.workspace,
        permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
    )

    if series.status != ChurchGatheringSeriesStatus.ACTIVE:
        raise ValidationError(
            "Only active gathering series can materialize occurrences."
        )

    created_occurrences = []
    day = from_date

    while day <= through_date:
        if _series_matches_date(series, day):
            starts_at, ends_at = _occurrence_window(series, day)

            occurrence, created = ChurchGatheringOccurrence.objects.get_or_create(
                series=series,
                starts_at=starts_at,
                defaults={
                    "workspace": series.workspace,
                    "campus": series.campus,
                    "ministry": series.ministry,
                    "title": series.name,
                    "gathering_type": series.gathering_type,
                    "location_label": series.location_label,
                    "visibility": series.visibility,
                    "ends_at": ends_at,
                    "source": ChurchGatheringOccurrenceSource.SERIES,
                    "created_by": actor,
                },
            )

            if created:
                occurrence.full_clean()
                created_occurrences.append(occurrence)
                record_church_audit(
                    workspace=series.workspace,
                    event=ChurchAuditEvent.GATHERING_CREATED,
                    actor=actor,
                    entity=occurrence,
                    metadata={
                        "source": occurrence.source,
                        "series_public_id": str(series.public_id),
                    },
                )

        day += timedelta(days=1)

    return created_occurrences


@transaction.atomic
def cancel_church_gathering(*, occurrence, actor, now=None):
    now = now or timezone.now()
    occurrence = (
        ChurchGatheringOccurrence.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=occurrence.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=occurrence.workspace,
        permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
    )

    if occurrence.status == ChurchGatheringOccurrenceStatus.CANCELED:
        return occurrence

    if occurrence.status == ChurchGatheringOccurrenceStatus.COMPLETED:
        raise ValidationError("Completed church gatherings cannot be canceled.")

    occurrence.status = ChurchGatheringOccurrenceStatus.CANCELED
    occurrence.canceled_at = now
    occurrence.canceled_by = actor
    occurrence.completed_at = None
    occurrence.completed_by = None
    occurrence.full_clean()
    occurrence.save()

    record_church_audit(
        workspace=occurrence.workspace,
        event=ChurchAuditEvent.GATHERING_CANCELED,
        actor=actor,
        entity=occurrence,
    )

    return occurrence


@transaction.atomic
def complete_church_gathering(*, occurrence, actor, now=None):
    now = now or timezone.now()
    occurrence = (
        ChurchGatheringOccurrence.objects
        .select_for_update()
        .select_related("workspace__activation__organization")
        .get(pk=occurrence.pk)
    )

    ensure_church_permission(
        actor=actor,
        workspace=occurrence.workspace,
        permission_key=ChurchPermissionKey.MANAGE_GATHERINGS,
    )

    if occurrence.status == ChurchGatheringOccurrenceStatus.COMPLETED:
        return occurrence

    if occurrence.status == ChurchGatheringOccurrenceStatus.CANCELED:
        raise ValidationError("Canceled church gatherings cannot be completed.")

    occurrence.status = ChurchGatheringOccurrenceStatus.COMPLETED
    occurrence.completed_at = now
    occurrence.completed_by = actor
    occurrence.canceled_at = None
    occurrence.canceled_by = None
    occurrence.full_clean()
    occurrence.save()

    record_church_audit(
        workspace=occurrence.workspace,
        event=ChurchAuditEvent.GATHERING_COMPLETED,
        actor=actor,
        entity=occurrence,
    )

    return occurrence
