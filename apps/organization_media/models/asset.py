# apps/organization_media/models/asset.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-10-19.

"""Reusable organization media metadata. Conversion runs in existing shared infrastructure."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.content_safety.enums import SafetyContext, SafetyInputType
from apps.content_safety.mixins import ContentSafetyMediaTargetMixin
from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_conversion import MediaConversionMixin

from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file


def organization_asset_upload_to(instance, filename):
    return f"organization_media/{instance.organization_id}/assets/{instance.public_id}/{filename}"


def organization_asset_thumbnail_upload_to(instance, filename):
    return f"organization_media/{instance.organization_id}/thumbnails/{instance.public_id}/{filename}"


class OrganizationMediaAsset(
    MediaAssetsMixin, ContentSafetyMediaTargetMixin,
    MediaAutoConvertMixin, MediaConversionMixin, models.Model,
):
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

    IMAGE_OUTPUT = FileUpload("organization_media", "photos", "assets")
    VIDEO_OUTPUT = FileUpload("organization_media", "videos", "assets")
    THUMBNAIL = FileUpload("organization_media", "photos", "asset_thumbnails")
    AUTO_THUMBNAIL_FROM_VIDEO = True

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="media_assets"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to=organization_asset_upload_to, max_length=700, validators=[validate_no_executable_file])
    thumbnail = models.ImageField(
        upload_to=organization_asset_thumbnail_upload_to, max_length=700,
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
    is_converted = models.BooleanField(default=False, db_index=True)
    image_safety_verified = models.BooleanField(default=False)
    upload_sha256 = models.CharField(max_length=64, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "status", "created_at"])]

    def clean(self):
        super().clean()
        if self.pk and self.status == self.Status.READY and not self.file:
            raise ValidationError({"file": "A ready asset requires a source file."})

    @property
    def media_conversion_config(self):
        # Deferred model construction must not trigger another database load.
        kind = self.__dict__.get("kind")
        if kind not in {self.Kind.IMAGE, self.Kind.VIDEO}:
            return {}
        return {
            "file": {
                "upload": self.VIDEO_OUTPUT if kind == self.Kind.VIDEO else self.IMAGE_OUTPUT,
                "kind": kind, "required_for_availability": True,
            },
            "thumbnail": {
                "upload": self.THUMBNAIL, "kind": "image",
                "required_for_availability": False,
            },
        }

    def get_content_safety_media_config(self):
        if self.kind != self.Kind.VIDEO:
            return {}
        return {"file": {
            "input_type": SafetyInputType.VIDEO, "context": SafetyContext.GENERIC,
            "conversion_kind": "video",
        }}

    def is_available(self):
        return bool(
            self.file and self.is_converted
            and self.status != self.Status.ARCHIVED
            and self.media_conversion_target_ready_for_availability()
        )

    def on_available(self):
        type(self).objects.filter(
            pk=self.pk, status=self.Status.PROCESSING, is_converted=True,
        ).update(status=self.Status.READY)
        if self.status == self.Status.PROCESSING:
            self.status = self.Status.READY

    def is_ready_for_publication(self):
        if self.status != self.Status.READY or not self.is_available():
            return False
        if self.kind == self.Kind.IMAGE:
            return self.image_safety_verified
        from apps.content_safety.enums import ContentSafetyJobStatus, SafetyDecision
        from apps.media_conversion.models import MediaJobStatus

        conversion = self._get_content_type()
        from apps.media_conversion.models import MediaConversionJob
        source = MediaConversionJob.objects.filter(
            content_type=conversion, object_id=self.pk, field_name="file",
            output_path=self.file.name, status=MediaJobStatus.DONE,
        ).order_by("-updated_at", "-id").first()
        return bool(source and self.content_safety_jobs.filter(
            field_name="file", source_path=source.source_path,
            status=ContentSafetyJobStatus.DONE, decision=SafetyDecision.ALLOW,
        ).exists())

    def can_manage_content_safety(self, *, actor):
        from apps.organization_content.services.access import can_manage_content
        return can_manage_content(actor=actor, organization=self.organization)

    def can_deliver_asset(self, *, viewer, field_name, intent):
        if field_name not in {"file", "thumbnail"} or intent == "download":
            return False
        if field_name == "thumbnail" and not self.thumbnail:
            return False
        from apps.organization_media.services.access import can_deliver_organization_asset
        return can_deliver_organization_asset(asset=self, viewer=viewer)

    def __str__(self):
        return f"{self.organization_id}:{self.kind}:{self.public_id}"

