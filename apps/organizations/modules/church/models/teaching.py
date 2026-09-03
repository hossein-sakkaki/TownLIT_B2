# apps/organizations/modules/church/models/teaching.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.organizations.modules.church.constants import (
    ChurchTeachingSeriesStatus,
)


class ChurchTeachingSeries(models.Model):
    """Durable Church teaching or sermon series."""

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
        related_name="teaching_series",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_series",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teaching_series",
    )

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=ChurchTeachingSeriesStatus.choices,
        default=ChurchTeachingSeriesStatus.ACTIVE,
        db_index=True,
    )
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Teaching Series"
        verbose_name_plural = "Church Teaching Series"
        ordering = ("sort_order", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="organizations_church_unique_teaching_series_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "sort_order"]),
            models.Index(fields=["campus", "status"]),
            models.Index(fields=["ministry", "status"]),
        ]

    def clean(self):
        super().clean()

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Teaching series campus must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != self.workspace_id:
            raise ValidationError({
                "ministry": "Teaching series ministry must belong to the same Church workspace.",
            })

        if (
            self.campus_id
            and self.ministry_id
            and self.ministry.campus_id
            and self.ministry.campus_id != self.campus_id
        ):
            raise ValidationError({
                "ministry": "Teaching series ministry belongs to a different campus.",
            })

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or "").split())
        self.description = str(self.description or "").strip()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workspace_id}:{self.name}"
