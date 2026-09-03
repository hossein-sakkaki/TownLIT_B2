# apps/organizations/modules/church/models/gathering.py
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

from apps.organizations.constants import OrganizationModuleVisibility
from apps.organizations.modules.church.constants import (
    ChurchGatheringOccurrenceSource,
    ChurchGatheringOccurrenceStatus,
    ChurchGatheringSeriesStatus,
    ChurchGatheringType,
    ChurchMonthlyWeek,
    ChurchRecurrenceFrequency,
)


class ChurchGatheringSeries(models.Model):
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
        related_name="gathering_series",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gathering_series",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gathering_series",
    )

    name = models.CharField(max_length=180)
    gathering_type = models.CharField(
        max_length=30,
        choices=ChurchGatheringType.choices,
        db_index=True,
    )
    description = models.CharField(max_length=1500, null=True, blank=True)
    location_label = models.CharField(max_length=250, null=True, blank=True)

    visibility = models.CharField(
        max_length=20,
        choices=OrganizationModuleVisibility.choices,
        default=OrganizationModuleVisibility.PUBLIC,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchGatheringSeriesStatus.choices,
        default=ChurchGatheringSeriesStatus.ACTIVE,
        db_index=True,
    )

    recurrence_frequency = models.CharField(
        max_length=20,
        choices=ChurchRecurrenceFrequency.choices,
        db_index=True,
    )
    weekday = models.PositiveSmallIntegerField()
    monthly_week = models.CharField(
        max_length=10,
        choices=ChurchMonthlyWeek.choices,
        null=True,
        blank=True,
    )
    local_start_time = models.TimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=90)
    effective_start_date = models.DateField(db_index=True)
    effective_end_date = models.DateField(null=True, blank=True, db_index=True)

    auto_create_attendance = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Gathering Series"
        verbose_name_plural = "Church Gathering Series"
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                check=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="organizations_church_gathering_weekday_range",
            ),
            models.CheckConstraint(
                check=Q(duration_minutes__gte=15) & Q(duration_minutes__lte=720),
                name="organizations_church_gathering_duration_range",
            ),
            models.CheckConstraint(
                check=(
                    Q(effective_end_date__isnull=True)
                    | Q(effective_end_date__gte=models.F("effective_start_date"))
                ),
                name="organizations_church_gathering_series_date_window",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "gathering_type"]),
            models.Index(fields=["campus", "status"]),
            models.Index(fields=["ministry", "status"]),
        ]

    def clean(self):
        super().clean()

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Gathering campus must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != self.workspace_id:
            raise ValidationError({
                "ministry": "Gathering ministry must belong to the same Church workspace.",
            })

        if (
            self.ministry_id
            and self.campus_id
            and self.ministry.campus_id
            and self.ministry.campus_id != self.campus_id
        ):
            raise ValidationError({
                "campus": "Gathering campus must match the ministry campus.",
            })

        if self.recurrence_frequency == ChurchRecurrenceFrequency.MONTHLY:
            if not self.monthly_week:
                raise ValidationError({
                    "monthly_week": "Monthly gathering series require a monthly week.",
                })
        elif self.monthly_week:
            raise ValidationError({
                "monthly_week": "Monthly week can only be used for monthly recurrence.",
            })

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or "").split())
        self.description = (
            str(self.description).strip()
            if self.description
            else None
        )
        self.location_label = (
            " ".join(str(self.location_label).split())
            if self.location_label
            else None
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workspace_id}:{self.name}"


class ChurchGatheringOccurrence(models.Model):
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
        related_name="gathering_occurrences",
    )
    series = models.ForeignKey(
        ChurchGatheringSeries,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="occurrences",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gathering_occurrences",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gathering_occurrences",
    )

    title = models.CharField(max_length=180)
    gathering_type = models.CharField(
        max_length=30,
        choices=ChurchGatheringType.choices,
        db_index=True,
    )
    location_label = models.CharField(max_length=250, null=True, blank=True)
    visibility = models.CharField(
        max_length=20,
        choices=OrganizationModuleVisibility.choices,
        default=OrganizationModuleVisibility.PUBLIC,
        db_index=True,
    )

    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)

    status = models.CharField(
        max_length=20,
        choices=ChurchGatheringOccurrenceStatus.choices,
        default=ChurchGatheringOccurrenceStatus.SCHEDULED,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=ChurchGatheringOccurrenceSource.choices,
        default=ChurchGatheringOccurrenceSource.MANUAL,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_church_gatherings",
    )
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="canceled_church_gatherings",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_church_gatherings",
    )

    canceled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Gathering Occurrence"
        verbose_name_plural = "Church Gathering Occurrences"
        ordering = ("starts_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["series", "starts_at"],
                name="organizations_church_unique_series_occurrence",
            ),
            models.CheckConstraint(
                check=Q(ends_at__gt=models.F("starts_at")),
                name="organizations_church_occurrence_time_window",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchGatheringOccurrenceStatus.SCHEDULED,
                        canceled_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchGatheringOccurrenceStatus.CANCELED,
                        canceled_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchGatheringOccurrenceStatus.COMPLETED,
                        canceled_at__isnull=True,
                        completed_at__isnull=False,
                    )
                ),
                name="organizations_church_occurrence_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "starts_at"]),
            models.Index(fields=["campus", "starts_at"]),
            models.Index(fields=["ministry", "starts_at"]),
        ]

    def clean(self):
        super().clean()

        if self.series_id and self.series.workspace_id != self.workspace_id:
            raise ValidationError({
                "series": "Gathering series must belong to the same Church workspace.",
            })

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Gathering campus must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != self.workspace_id:
            raise ValidationError({
                "ministry": "Gathering ministry must belong to the same Church workspace.",
            })

        if self.series_id:
            if self.gathering_type != self.series.gathering_type:
                raise ValidationError({
                    "gathering_type": "Series occurrences must use the series gathering type.",
                })
            if self.source != ChurchGatheringOccurrenceSource.SERIES:
                raise ValidationError({
                    "source": "Series occurrences must use the recurring-series source.",
                })

    def save(self, *args, **kwargs):
        self.title = " ".join(str(self.title or "").split())
        self.location_label = (
            " ".join(str(self.location_label).split())
            if self.location_label
            else None
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workspace_id}:{self.title}:{self.starts_at}"
