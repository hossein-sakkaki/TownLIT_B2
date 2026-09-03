# apps/organizations/modules/church/models/service_plan.py
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
    ChurchServicePlanItemType,
    ChurchServicePlanStatus,
)


class ChurchServicePlan(models.Model):
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
        related_name="service_plans",
    )
    occurrence = models.OneToOneField(
        "organizations.ChurchGatheringOccurrence",
        on_delete=models.CASCADE,
        related_name="service_plan",
    )

    theme = models.CharField(max_length=180, null=True, blank=True)
    internal_notes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ChurchServicePlanStatus.choices,
        default=ChurchServicePlanStatus.DRAFT,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_service_plans_created",
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_service_plans_published",
    )
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_service_plans_completed",
    )
    canceled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_service_plans_canceled",
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Service Plan"
        verbose_name_plural = "Church Service Plans"
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchServicePlanStatus.DRAFT,
                        published_at__isnull=True,
                        completed_at__isnull=True,
                        canceled_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServicePlanStatus.PUBLISHED,
                        published_at__isnull=False,
                        completed_at__isnull=True,
                        canceled_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServicePlanStatus.COMPLETED,
                        published_at__isnull=False,
                        completed_at__isnull=False,
                        canceled_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServicePlanStatus.CANCELED,
                        completed_at__isnull=True,
                        canceled_at__isnull=False,
                    )
                ),
                name="organizations_church_service_plan_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "created_at"]),
        ]

    def clean(self):
        super().clean()

        if self.occurrence.workspace_id != self.workspace_id:
            raise ValidationError({
                "occurrence": "Service plan occurrence must belong to the same Church workspace.",
            })

    def save(self, *args, **kwargs):
        self.theme = " ".join(str(self.theme).split()) if self.theme else None
        self.internal_notes = (
            str(self.internal_notes).strip()
            if self.internal_notes
            else None
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.occurrence_id}:{self.status}"


class ChurchServicePlanItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    service_plan = models.ForeignKey(
        ChurchServicePlan,
        on_delete=models.CASCADE,
        related_name="items",
    )
    serving_team = models.ForeignKey(
        "organizations.ChurchServingTeam",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_plan_items",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_plan_items",
    )

    item_type = models.CharField(
        max_length=30,
        choices=ChurchServicePlanItemType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=180)
    notes = models.CharField(max_length=1500, null=True, blank=True)
    planned_duration_seconds = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=100, db_index=True)
    is_optional = models.BooleanField(default=False)
    is_internal_only = models.BooleanField(default=False)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Service Plan Item"
        verbose_name_plural = "Church Service Plan Items"
        ordering = ("sort_order", "id")
        constraints = [
            models.CheckConstraint(
                check=Q(planned_duration_seconds__lte=14400),
                name="organizations_church_service_item_duration_range",
            ),
        ]
        indexes = [
            models.Index(fields=["service_plan", "sort_order"]),
            models.Index(fields=["service_plan", "item_type"]),
        ]

    def clean(self):
        super().clean()
        workspace_id = self.service_plan.workspace_id

        if self.serving_team_id and self.serving_team.workspace_id != workspace_id:
            raise ValidationError({
                "serving_team": "Service plan item team must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != workspace_id:
            raise ValidationError({
                "ministry": "Service plan item ministry must belong to the same Church workspace.",
            })

    def save(self, *args, **kwargs):
        self.title = " ".join(str(self.title or "").split())
        self.notes = str(self.notes).strip() if self.notes else None
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service_plan_id}:{self.sort_order}:{self.title}"
