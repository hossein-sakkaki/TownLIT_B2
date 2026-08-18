# apps/bookstore_inventory/models/organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

import re
import unicodedata
from uuid import uuid4

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.bookstore_inventory.constants import OrganizationRoleType, ProfileLinkStatus
from apps.bookstore_inventory.models.base import TimeStampedModel


def normalize_organization_name(value):
    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


class OrganizationRecord(TimeStampedModel):
    """Stable internal identity; independent from any future public profile."""

    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    official_name = models.CharField(max_length=255, db_index=True)
    display_name = models.CharField(max_length=255, blank=True, db_index=True)
    normalized_name = models.CharField(max_length=255, editable=False, db_index=True)
    registration_number = models.CharField(max_length=120, blank=True, db_index=True)
    tax_identifier = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True, db_index=True)
    province_state = models.CharField(max_length=120, blank=True, db_index=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=120, blank=True, db_index=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    merged_into = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="merged_records",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("display_name", "official_name", "id")
        indexes = [
            models.Index(fields=("normalized_name", "country")),
            models.Index(fields=("registration_number", "country")),
        ]
        verbose_name = "Organization record"
        verbose_name_plural = "Organization directory"

    def __str__(self):
        return self.display_name or self.official_name

    def clean(self):
        if self.merged_into_id == self.pk:
            raise ValidationError({"merged_into": "An organization cannot be merged into itself."})
        if self.merged_into_id and self.is_active:
            raise ValidationError({"is_active": "A merged organization must be inactive."})

    def save(self, *args, **kwargs):
        self.official_name = self.official_name.strip()
        self.display_name = self.display_name.strip()
        self.normalized_name = normalize_organization_name(self.official_name)
        super().save(*args, **kwargs)


class OrganizationAlias(TimeStampedModel):
    organization = models.ForeignKey(
        OrganizationRecord, on_delete=models.CASCADE, related_name="aliases"
    )
    name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, editable=False, db_index=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "normalized_name"),
                name="bookstore_unique_organization_alias",
            )
        ]
        verbose_name = "Organization alias"
        verbose_name_plural = "Organization aliases"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.normalized_name = normalize_organization_name(self.name)
        super().save(*args, **kwargs)


class OrganizationRole(TimeStampedModel):
    organization = models.ForeignKey(
        OrganizationRecord, on_delete=models.CASCADE, related_name="roles"
    )
    role = models.CharField(max_length=40, choices=OrganizationRoleType.choices, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("organization", "role")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "role"),
                name="bookstore_unique_organization_role",
            )
        ]
        verbose_name = "Organization role"
        verbose_name_plural = "Organization roles"

    def __str__(self):
        return f"{self.organization} — {self.get_role_display()}"


class OrganizationProfileLink(TimeStampedModel):
    """Optional verified bridge to a future public organization profile."""

    organization = models.ForeignKey(
        OrganizationRecord, on_delete=models.CASCADE, related_name="profile_links"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    profile = GenericForeignKey("content_type", "object_id")
    status = models.CharField(
        max_length=24, choices=ProfileLinkStatus.choices,
        default=ProfileLinkStatus.PENDING, db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookstore_organization_links_requested",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookstore_organization_links_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    evidence = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("content_type", "object_id"),
                name="bookstore_unique_external_org_profile",
            )
        ]
        indexes = [models.Index(fields=("content_type", "object_id"))]
        verbose_name = "Organization profile link"
        verbose_name_plural = "Organization profile links"

    def __str__(self):
        return f"{self.organization} — {self.content_type}:{self.object_id}"
