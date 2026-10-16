# apps/organization_media/models/asset.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

"""Reusable organization media metadata. Conversion runs in existing shared infrastructure."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file


def organization_asset_upload_to(instance, filename):
    return f"organization_media/{instance.organization_id}/assets/{instance.public_id}/{filename}"


def organization_asset_thumbnail_upload_to(instance, filename):
    return f"organization_media/{instance.organization_id}/thumbnails/{instance.public_id}/{filename}"


class OrganizationMediaAsset(models.Model):
    """A reusable asset belonging to exactly one Organization, not to a specific module."""

    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        ARCHIVED = "archived", "Archived"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="media_assets"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to=organization_asset_upload_to, validators=[validate_no_executable_file])
    thumbnail = models.ImageField(
        upload_to=organization_asset_thumbnail_upload_to,
        blank=True, null=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
    )
    alt_text = models.CharField(max_length=300, blank=True)
    caption = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="organization_media_assets_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "status", "created_at"])]

    def clean(self):
        super().clean()
        if self.pk and self.status == self.Status.READY and not self.file:
            raise ValidationError({"file": "A ready asset requires a source file."})

    def __str__(self):
        return f"{self.organization_id}:{self.kind}:{self.public_id}"
