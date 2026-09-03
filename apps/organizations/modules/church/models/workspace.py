# apps/organizations/modules/church/models/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.organizations.constants import OrganizationModuleKey


class ChurchWorkspace(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    activation = models.OneToOneField(
        "organizations.OrganizationModuleActivation",
        on_delete=models.CASCADE,
        related_name="church_workspace",
    )

    timezone_override = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    membership_directory_enabled = models.BooleanField(default=False)
    attendance_tracking_enabled = models.BooleanField(default=True)
    default_gathering_duration_minutes = models.PositiveSmallIntegerField(
        default=90,
    )

    settings = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Workspace"
        verbose_name_plural = "Church Workspaces"
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(default_gathering_duration_minutes__gte=15)
                    & Q(default_gathering_duration_minutes__lte=720)
                ),
                name="organizations_church_workspace_duration_range",
            ),
        ]

    def clean(self):
        super().clean()

        if self.activation.module.key != OrganizationModuleKey.CHURCH:
            raise ValidationError({
                "activation": (
                    "Church workspaces require a Church module activation."
                ),
            })

        if self.timezone_override:
            try:
                ZoneInfo(self.timezone_override)
            except ZoneInfoNotFoundError as exc:
                raise ValidationError({
                    "timezone_override": "Unknown IANA timezone.",
                }) from exc

    @property
    def organization(self):
        return self.activation.organization

    @property
    def effective_timezone(self) -> str:
        return (
            self.timezone_override
            or self.activation.organization.timezone
            or "UTC"
        )

    def __str__(self):
        return f"{self.activation.organization_id}:church"
