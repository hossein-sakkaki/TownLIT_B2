# apps/organizations/modules/church/models/attendance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchAttendancePresence,
    ChurchAttendanceSessionStatus,
    ChurchAttendanceSource,
)


class ChurchAttendanceSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    workspace = models.ForeignKey(
        "organizations.ChurchWorkspace",
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
    )
    occurrence = models.OneToOneField(
        "organizations.ChurchGatheringOccurrence",
        on_delete=models.CASCADE,
        related_name="attendance_session",
    )

    status = models.CharField(
        max_length=20,
        choices=ChurchAttendanceSessionStatus.choices,
        default=ChurchAttendanceSessionStatus.OPEN,
        db_index=True,
    )

    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_church_attendance_sessions",
    )
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_church_attendance_sessions",
    )

    unregistered_adult_count = models.PositiveIntegerField(default=0)
    unregistered_child_count = models.PositiveIntegerField(default=0)
    anonymous_online_count = models.PositiveIntegerField(default=0)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Attendance Session"
        verbose_name_plural = "Church Attendance Sessions"
        ordering = ("-opened_at", "id")
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchAttendanceSessionStatus.OPEN,
                        closed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchAttendanceSessionStatus.CLOSED,
                        closed_at__isnull=False,
                    )
                ),
                name="organizations_church_attendance_session_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "opened_at"]),
        ]

    def clean(self):
        super().clean()

        if self.occurrence.workspace_id != self.workspace_id:
            raise ValidationError({
                "occurrence": "Attendance occurrence must belong to the same Church workspace.",
            })

    @property
    def registered_attendee_count(self) -> int:
        return self.records.count()

    @property
    def aggregate_guest_count(self) -> int:
        return (
            self.unregistered_adult_count
            + self.unregistered_child_count
            + self.anonymous_online_count
        )

    @property
    def total_attendance_count(self) -> int:
        return self.registered_attendee_count + self.aggregate_guest_count

    def __str__(self):
        return f"{self.occurrence_id}:{self.status}"


class ChurchAttendanceRecord(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    session = models.ForeignKey(
        ChurchAttendanceSession,
        on_delete=models.CASCADE,
        related_name="records",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="church_attendance_records",
    )

    presence = models.CharField(
        max_length=20,
        choices=ChurchAttendancePresence.choices,
        default=ChurchAttendancePresence.PRESENT,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=ChurchAttendanceSource.choices,
        default=ChurchAttendanceSource.MANUAL,
        db_index=True,
    )

    checked_in_at = models.DateTimeField(default=timezone.now, db_index=True)
    checked_out_at = models.DateTimeField(null=True, blank=True, db_index=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_church_attendance",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Attendance Record"
        verbose_name_plural = "Church Attendance Records"
        ordering = ("checked_in_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["session", "membership"],
                name="organizations_church_unique_attendance_record",
            ),
            models.CheckConstraint(
                check=(
                    Q(checked_out_at__isnull=True)
                    | Q(checked_out_at__gt=models.F("checked_in_at"))
                ),
                name="organizations_church_attendance_checkout_window",
            ),
        ]
        indexes = [
            models.Index(fields=["session", "presence"]),
            models.Index(fields=["membership", "checked_in_at"]),
        ]

    def clean(self):
        super().clean()

        organization_id = self.session.workspace.activation.organization_id

        if self.membership.organization_id != organization_id:
            raise ValidationError({
                "membership": "Attendance membership must belong to the same organization.",
            })

        if self.membership.status != OrganizationMembershipStatus.ACTIVE:
            raise ValidationError({
                "membership": "Attendance can only be recorded for active organization members.",
            })

    def __str__(self):
        return f"{self.session_id}:{self.membership_id}:{self.presence}"
