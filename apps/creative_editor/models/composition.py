# apps/creative_editor/models/composition.py

from __future__ import annotations

import hashlib
import json

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.creative_editor.validators.document import (
    DOCUMENT_VERSION,
    validate_creative_document,
)
from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_conversion import MediaConversionMixin
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_moment_image_size,
)
from validators.security_validators import validate_no_executable_file

from .base import PublicIDTimestampedModel


class CreativeComposition(
    MediaAssetsMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    PublicIDTimestampedModel,
):
    """
    A reusable, versioned creative editor document.
    """

    SOURCE_IMAGE = FileUpload(
        "creative_editor",
        "sources",
        "compositions",
    )
    RENDERED_IMAGE = FileUpload(
        "creative_editor",
        "renders",
        "compositions",
    )
    RENDERED_VIDEO = FileUpload(
        "creative_editor",
        "renders",
        "compositions",
    )
    THUMBNAIL_IMAGE = FileUpload(
        "creative_editor",
        "thumbnails",
        "compositions",
    )

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RENDERING = "rendering", "Rendering"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        ARCHIVED = "archived", "Archived"

    class SourceMode(models.TextChoices):
        UPLOAD = "upload", "Uploaded Image"
        CONTENT_REFERENCE = "content_reference", "Content Reference"
        GENERATED_BACKGROUND = (
            "generated_background",
            "Generated Background",
        )

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        AUTHENTICATED = "authenticated", "Authenticated"
        PUBLIC = "public", "Public"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creative_compositions",
    )
    title = models.CharField(max_length=160, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
        db_index=True,
    )
    source_mode = models.CharField(
        max_length=32,
        choices=SourceMode.choices,
        default=SourceMode.GENERATED_BACKGROUND,
        db_index=True,
    )

    # -------------------------------------------------
    # Uploaded source
    # -------------------------------------------------
    source_image = models.ImageField(
        upload_to=SOURCE_IMAGE.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_moment_image_size,
            validate_no_executable_file,
        ],
    )
    source_image_is_converted = models.BooleanField(
        default=False,
        db_index=True,
    )

    # -------------------------------------------------
    # Existing media reference
    # -------------------------------------------------
    source_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="creative_source_compositions",
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    source_content_object = GenericForeignKey(
        "source_content_type",
        "source_object_id",
    )
    source_field_name = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    # -------------------------------------------------
    # Canvas
    # -------------------------------------------------
    canvas_width = models.PositiveIntegerField(default=1080)
    canvas_height = models.PositiveIntegerField(default=1920)
    format_version = models.PositiveIntegerField(default=DOCUMENT_VERSION)
    revision = models.PositiveIntegerField(default=1, db_index=True)
    document = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_creative_document],
    )
    document_sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    # -------------------------------------------------
    # Canonical render output
    # -------------------------------------------------
    rendered_image = models.ImageField(
        upload_to=RENDERED_IMAGE.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_no_executable_file,
        ],
    )

    rendered_video = models.FileField(
        upload_to=RENDERED_VIDEO.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_no_executable_file,
        ],
    )

    thumbnail = models.ImageField(
        upload_to=THUMBNAIL_IMAGE.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_no_executable_file,
        ],
    )

    rendered_revision = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    rendered_at = models.DateTimeField(null=True, blank=True)
    render_error = models.TextField(blank=True, default="")

    # -------------------------------------------------
    # General state
    # -------------------------------------------------
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    media_conversion_config = {
        "source_image": {
            "upload": SOURCE_IMAGE,
            "kind": "image",
        },
    }

    MEDIA_FLAG_FIELD = "source_image_is_converted"

    def clean(self):
        super().clean()

        self._validate_source()
        self._validate_canvas()
        self._validate_document_consistency()

    def _validate_source(self) -> None:
        has_upload = bool(self.source_image)

        has_reference = bool(
            self.source_content_type_id
            and self.source_object_id
            and self.source_field_name.strip()
        )

        if self.source_mode == self.SourceMode.UPLOAD:
            if not has_upload:
                raise ValidationError(
                    {
                        "source_image": (
                            "Uploaded source mode requires a source image."
                        ),
                    }
                )

            if has_reference:
                raise ValidationError(
                    "Uploaded source mode cannot use a content reference."
                )

        elif self.source_mode == self.SourceMode.CONTENT_REFERENCE:
            if not has_reference:
                raise ValidationError(
                    "Content reference mode requires a complete source target."
                )

            if has_upload:
                raise ValidationError(
                    "Content reference mode cannot use an uploaded source."
                )

        elif self.source_mode == self.SourceMode.GENERATED_BACKGROUND:
            if has_upload or has_reference:
                raise ValidationError(
                    "Generated background mode cannot use source media."
                )

    def _validate_canvas(self) -> None:
        if self.canvas_width > 8192:
            raise ValidationError(
                {"canvas_width": "Canvas width cannot exceed 8192."}
            )

        if self.canvas_height > 8192:
            raise ValidationError(
                {"canvas_height": "Canvas height cannot exceed 8192."}
            )

    def _validate_document_consistency(self) -> None:
        if not self.document:
            raise ValidationError(
                {"document": "Creative document is required."}
            )

        document_canvas = self.document.get("canvas", {})

        if document_canvas.get("width") != self.canvas_width:
            raise ValidationError(
                {
                    "document": (
                        "Document canvas width does not match the composition."
                    ),
                }
            )

        if document_canvas.get("height") != self.canvas_height:
            raise ValidationError(
                {
                    "document": (
                        "Document canvas height does not match the composition."
                    ),
                }
            )

        if self.document.get("version") != self.format_version:
            raise ValidationError(
                {
                    "document": (
                        "Document version does not match format_version."
                    ),
                }
            )

    def media_autoconvert_enabled(self) -> bool:
        return bool(
            self.source_mode == self.SourceMode.UPLOAD
            and self.source_image
        )

    def save(self, *args, **kwargs):
        self.document_sha256 = self.build_document_hash()
        super().save(*args, **kwargs)

    def build_document_hash(self) -> str:
        payload = json.dumps(
            self.document or {},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        return hashlib.sha256(payload).hexdigest()

    def has_current_render(self) -> bool:
        return bool(
            (self.rendered_image or self.rendered_video)
            and self.rendered_revision == self.revision
            and self.status == self.Status.READY
        )

    @property
    def rendered_media_type(self) -> str | None:
        if self.rendered_video:
            return "video"

        if self.rendered_image:
            return "image"

        return None


    @property
    def rendered_field_name(self) -> str | None:
        if self.rendered_video:
            return "rendered_video"

        if self.rendered_image:
            return "rendered_image"

        return None


    @property
    def rendered_file(self):
        field_name = self.rendered_field_name

        if not field_name:
            return None

        return getattr(
            self,
            field_name,
            None,
        )
        
    def is_available(self) -> bool:
        return bool(
            self.is_active
            and self.has_current_render()
        )

    def can_deliver_asset(
        self,
        *,
        viewer,
        field_name: str,
        intent: str,
    ) -> bool:
        """
        Authorize composition asset delivery.
        """

        if field_name not in {
            "source_image",
            "rendered_image",
            "rendered_video",
            "thumbnail",
        }:
            return False

        is_authenticated = bool(
            viewer
            and getattr(viewer, "is_authenticated", False)
        )
        is_owner = bool(
            is_authenticated
            and viewer.pk == self.owner_id
        )
        is_staff = bool(
            is_authenticated
            and getattr(viewer, "is_staff", False)
        )

        if field_name == "source_image":
            return bool(
                self.source_image
                and (is_owner or is_staff)
            )

        if not self.is_available():
            return False

        if is_owner or is_staff:
            return True

        if self.visibility == self.Visibility.PUBLIC:
            return True

        if self.visibility == self.Visibility.AUTHENTICATED:
            return is_authenticated

        return False

    def __str__(self) -> str:
        label = self.title.strip() or str(self.public_id)
        return f"Composition · {label}"

    class Meta:
        verbose_name = "Creative Composition"
        verbose_name_plural = "Creative Compositions"
        ordering = ("-updated_at", "-id")

        indexes = [
            models.Index(
                fields=("owner", "status", "-updated_at"),
                name="creative_comp_owner_status_idx",
            ),
            models.Index(
                fields=("visibility", "status", "is_active"),
                name="creative_comp_delivery_idx",
            ),
            models.Index(
                fields=("source_content_type", "source_object_id"),
                name="creative_comp_source_idx",
            ),
            models.Index(
                fields=("status", "rendered_revision", "revision"),
                name="creative_comp_render_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(canvas_width__gt=0),
                name="creative_canvas_width_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(canvas_height__gt=0),
                name="creative_canvas_height_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(format_version__gt=0),
                name="creative_format_version_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(revision__gt=0),
                name="creative_revision_gt_zero",
            ),
            models.CheckConstraint(
                check=(
                    Q(rendered_revision__isnull=True)
                    | Q(rendered_revision__gt=0)
                ),
                name="creative_rendered_revision_valid",
            ),
        ]