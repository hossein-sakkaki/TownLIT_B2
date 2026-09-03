# apps/organizations/modules/church/models/resource.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.organizations.modules.church.constants import (
    ChurchResourceReservationStatus,
    ChurchResourceStatus,
    ChurchResourceType,
)


class ChurchResource(models.Model):
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
        related_name="resources",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )

    resource_type = models.CharField(
        max_length=20,
        choices=ChurchResourceType.choices,
        db_index=True,
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, allow_unicode=False)
    description = models.CharField(max_length=1500, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=ChurchResourceStatus.choices,
        default=ChurchResourceStatus.ACTIVE,
        db_index=True,
    )
    is_reservable = models.BooleanField(default=True, db_index=True)
    quantity_available = models.PositiveIntegerField(default=1)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Resource"
        verbose_name_plural = "Church Resources"
        ordering = ("sort_order", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="organizations_church_unique_resource_slug",
            ),
            models.CheckConstraint(
                check=Q(quantity_available__gte=1),
                name="organizations_church_resource_quantity_positive",
            ),
            models.CheckConstraint(
                check=Q(capacity__isnull=True) | Q(capacity__gte=1),
                name="organizations_church_resource_capacity_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "resource_type"]),
            models.Index(fields=["campus", "status"]),
            models.Index(fields=["ministry", "status"]),
        ]

    def clean(self):
        super().clean()

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Church resource campus must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != self.workspace_id:
            raise ValidationError({
                "ministry": "Church resource ministry must belong to the same Church workspace.",
            })

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or "").split())
        self.description = (
            str(self.description).strip()
            if self.description
            else None
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workspace_id}:{self.slug}"


class ChurchResourceReservation(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    resource = models.ForeignKey(
        ChurchResource,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    occurrence = models.ForeignKey(
        "organizations.ChurchGatheringOccurrence",
        on_delete=models.CASCADE,
        related_name="resource_reservations",
    )

    quantity = models.PositiveIntegerField(default=1)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=ChurchResourceReservationStatus.choices,
        default=ChurchResourceReservationStatus.RESERVED,
        db_index=True,
    )

    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_resource_reservations_created",
    )
    canceled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_resource_reservations_canceled",
    )
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_resource_reservations_completed",
    )

    notes = models.CharField(max_length=1000, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Resource Reservation"
        verbose_name_plural = "Church Resource Reservations"
        ordering = ("starts_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "occurrence"],
                name="organizations_church_unique_resource_occurrence",
            ),
            models.CheckConstraint(
                check=Q(quantity__gte=1),
                name="organizations_church_resource_reservation_quantity_positive",
            ),
            models.CheckConstraint(
                check=Q(ends_at__gt=models.F("starts_at")),
                name="organizations_church_resource_reservation_time_window",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchResourceReservationStatus.RESERVED,
                        canceled_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchResourceReservationStatus.CANCELED,
                        canceled_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchResourceReservationStatus.COMPLETED,
                        canceled_at__isnull=True,
                        completed_at__isnull=False,
                    )
                ),
                name="organizations_church_resource_reservation_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["resource", "status", "starts_at"]),
            models.Index(fields=["occurrence", "status"]),
        ]

    def clean(self):
        super().clean()

        if self.occurrence.workspace_id != self.resource.workspace_id:
            raise ValidationError({
                "occurrence": "Resource reservation occurrence must belong to the same Church workspace.",
            })

        if self.quantity > self.resource.quantity_available:
            raise ValidationError({
                "quantity": "Reservation quantity exceeds the resource quantity available.",
            })

    def save(self, *args, **kwargs):
        self.notes = str(self.notes).strip() if self.notes else None
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.resource_id}:{self.occurrence_id}:{self.status}"
