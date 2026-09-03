# apps/organizations/modules/church/models/campus.py
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

from apps.organizations.modules.church.constants import ChurchCampusStatus


class ChurchCampus(models.Model):
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
        related_name="campuses",
    )

    name = models.CharField(max_length=160)
    slug = models.SlugField(
        max_length=180,
        allow_unicode=False,
    )
    description = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )

    address = models.ForeignKey(
        "accounts.Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_campuses",
    )

    public_email = models.EmailField(null=True, blank=True)
    public_phone = models.CharField(max_length=30, null=True, blank=True)
    website_url = models.URLField(max_length=500, null=True, blank=True)
    timezone_override = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=ChurchCampusStatus.choices,
        default=ChurchCampusStatus.ACTIVE,
        db_index=True,
    )
    is_primary = models.BooleanField(default=False, db_index=True)

    # MySQL-safe uniqueness slot for the active primary campus.
    primary_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    sort_order = models.PositiveSmallIntegerField(default=100, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Campus"
        verbose_name_plural = "Church Campuses"
        ordering = ("sort_order", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="organizations_church_unique_campus_slug",
            ),
            models.UniqueConstraint(
                fields=["workspace", "primary_slot"],
                name="organizations_church_unique_primary_campus",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "sort_order"]),
        ]

    def _sync_primary_slot(self):
        self.primary_slot = (
            1
            if self.is_primary and self.status == ChurchCampusStatus.ACTIVE
            else None
        )

    def clean(self):
        super().clean()
        self._sync_primary_slot()

        if self.is_primary and self.status != ChurchCampusStatus.ACTIVE:
            raise ValidationError({
                "is_primary": "Only active campuses can be primary.",
            })

        if self.timezone_override:
            try:
                ZoneInfo(self.timezone_override)
            except ZoneInfoNotFoundError as exc:
                raise ValidationError({
                    "timezone_override": "Unknown IANA timezone.",
                }) from exc

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or "").split())
        self.description = (
            str(self.description).strip()
            if self.description
            else None
        )
        self._sync_primary_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "primary_slot",
            }

        return super().save(*args, **kwargs)

    @property
    def effective_timezone(self) -> str:
        return self.timezone_override or self.workspace.effective_timezone

    def __str__(self):
        return f"{self.workspace_id}:{self.slug}"
