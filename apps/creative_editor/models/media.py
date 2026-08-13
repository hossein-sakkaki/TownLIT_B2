#
#  apps/creative_editor/models/media.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-10.
#  Last Update by Hossein Sakkaki on 2026-08-11.
#

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

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


class CreativeCompositionMedia(
    MediaAssetsMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    PublicIDTimestampedModel,
):
    """
    One immutable source media asset owned by a composition.
    """

    SOURCE_IMAGE = FileUpload(
        "creative_editor",
        "sources",
        "media",
    )

    SOURCE_VIDEO = FileUpload(
        "creative_editor",
        "sources",
        "media",
    )

    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class SourceMode(models.TextChoices):
        UPLOAD = "upload", "Upload"
        CONTENT_REFERENCE = "content_reference", "Content Reference"

    composition = models.ForeignKey(
        "creative_editor.CreativeComposition",
        on_delete=models.CASCADE,
        related_name="source_media",
    )

    media_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
        db_index=True,
    )

    source_mode = models.CharField(
        max_length=32,
        choices=SourceMode.choices,
        default=SourceMode.UPLOAD,
        db_index=True,
    )

    # -------------------------------------------------
    # Uploaded image
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
    # Uploaded video
    # -------------------------------------------------

    source_video = models.FileField(
        upload_to=SOURCE_VIDEO.dir_upload,
        max_length=700,
        null=True,
        blank=True,
        validators=[
            validate_no_executable_file,
        ],
    )

    source_video_is_converted = models.BooleanField(
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
        related_name="creative_composition_media_sources",
    )

    source_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

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
    # Shared media metadata
    # -------------------------------------------------

    width = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    height = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    media_conversion_config = {
        "source_image": {
            "upload": SOURCE_IMAGE,
            "kind": "image",
        },
        "source_video": {
            "upload": SOURCE_VIDEO,
            "kind": "video",
        },
    }

    # Retained for legacy mixin compatibility.
    MEDIA_FLAG_FIELD = "source_image_is_converted"

    def clean(self) -> None:
        super().clean()

        self.source_field_name = str(
            self.source_field_name or ""
        ).strip()

        self._validate_media_type()
        self._validate_source()

    def _validate_media_type(self) -> None:
        if self.media_type in {
            self.MediaType.IMAGE,
            self.MediaType.VIDEO,
        }:
            return

        raise ValidationError(
            {
                "media_type": (
                    "Unsupported creative media type."
                ),
            }
        )

    def _validate_source(self) -> None:
        has_image = bool(
            self.source_image
        )

        has_video = bool(
            self.source_video
        )

        has_reference = bool(
            self.source_content_type_id
            and self.source_object_id
            and self.source_field_name
        )

        if self.source_mode == self.SourceMode.UPLOAD:
            if has_reference:
                raise ValidationError(
                    "Uploaded media cannot use a content reference."
                )

            if self.media_type == self.MediaType.IMAGE:
                if not has_image:
                    raise ValidationError(
                        {
                            "source_image": (
                                "Uploaded image media requires "
                                "a source image."
                            ),
                        }
                    )

                if has_video:
                    raise ValidationError(
                        {
                            "source_video": (
                                "Image media cannot contain "
                                "a source video."
                            ),
                        }
                    )

                return

            if self.media_type == self.MediaType.VIDEO:
                if not has_video:
                    raise ValidationError(
                        {
                            "source_video": (
                                "Uploaded video media requires "
                                "a source video."
                            ),
                        }
                    )

                if has_image:
                    raise ValidationError(
                        {
                            "source_image": (
                                "Video media cannot contain "
                                "a source image."
                            ),
                        }
                    )

                if not self.duration_ms:
                    raise ValidationError(
                        {
                            "duration_ms": (
                                "Uploaded video media requires "
                                "a validated duration."
                            ),
                        }
                    )

                return

        if self.source_mode == self.SourceMode.CONTENT_REFERENCE:
            if has_image or has_video:
                raise ValidationError(
                    "Content reference media cannot use an upload."
                )

            if not has_reference:
                raise ValidationError(
                    {
                        "source_content_type": (
                            "Content reference media requires "
                            "a complete source target."
                        ),
                    }
                )

            return

        raise ValidationError(
            {
                "source_mode": (
                    "Unsupported creative media source mode."
                ),
            }
        )

    # -------------------------------------------------
    # Field-aware conversion flags
    # -------------------------------------------------

    def _conversion_flag_field(self) -> str:
        if self.media_type == self.MediaType.VIDEO:
            return "source_video_is_converted"

        return "source_image_is_converted"

    def _get_flag_value(self) -> bool:
        return bool(
            getattr(
                self,
                self._conversion_flag_field(),
                False,
            )
        )

    def _set_flag_value(
        self,
        value: bool,
    ) -> None:
        setattr(
            self,
            self._conversion_flag_field(),
            bool(value),
        )

    def media_autoconvert_enabled(self) -> bool:
        if self.source_mode != self.SourceMode.UPLOAD:
            return False

        if self.media_type == self.MediaType.IMAGE:
            return bool(
                self.source_image
            )

        if self.media_type == self.MediaType.VIDEO:
            return bool(
                self.source_video
            )

        return False

    def is_available(self) -> bool:
        if not self.is_active:
            return False

        if self.source_mode == self.SourceMode.UPLOAD:
            if self.media_type == self.MediaType.IMAGE:
                return bool(
                    self.source_image
                    and self.source_image_is_converted
                )

            if self.media_type == self.MediaType.VIDEO:
                return bool(
                    self.source_video
                    and self.source_video_is_converted
                )

            return False

        if self.source_mode == self.SourceMode.CONTENT_REFERENCE:
            target = self.source_content_object

            if target is None or not self.source_field_name:
                return False

            field = getattr(
                target,
                self.source_field_name,
                None,
            )

            return bool(
                field
                and getattr(
                    field,
                    "name",
                    None,
                )
            )

        return False

    def can_deliver_asset(
        self,
        *,
        viewer,
        field_name: str,
        intent: str,
    ) -> bool:
        """
        Uploaded editor sources remain owner-private.
        """

        expected_field = (
            "source_video"
            if self.media_type == self.MediaType.VIDEO
            else "source_image"
        )

        if field_name != expected_field:
            return False

        if self.source_mode != self.SourceMode.UPLOAD:
            return False

        source = getattr(
            self,
            expected_field,
            None,
        )

        if not source:
            return False

        is_authenticated = bool(
            viewer
            and getattr(
                viewer,
                "is_authenticated",
                False,
            )
        )

        if not is_authenticated:
            return False

        if getattr(
            viewer,
            "is_staff",
            False,
        ):
            return True

        return (
            viewer.pk
            == self.composition.owner_id
        )

    def on_media_converted(
        self,
        field_name: str,
        update_fields: list[str],
    ) -> None:
        """
        Persist field-specific conversion readiness.
        """

        if (
            field_name == "source_image"
            and self.media_type == self.MediaType.IMAGE
            and self.source_mode == self.SourceMode.UPLOAD
        ):
            self.source_image_is_converted = True

            if "source_image_is_converted" not in update_fields:
                update_fields.append(
                    "source_image_is_converted"
                )

            return

        if (
            field_name == "source_video"
            and self.media_type == self.MediaType.VIDEO
            and self.source_mode == self.SourceMode.UPLOAD
        ):
            self.source_video_is_converted = True

            if "source_video_is_converted" not in update_fields:
                update_fields.append(
                    "source_video_is_converted"
                )

    def __str__(self) -> str:
        return (
            f"Creative Media · {self.media_type} · "
            f"{self.public_id}"
        )

    class Meta:
        verbose_name = "Creative Composition Media"
        verbose_name_plural = "Creative Composition Media"

        ordering = (
            "created_at",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "composition",
                    "is_active",
                    "created_at",
                ),
                name="creative_media_comp_active_idx",
            ),
            models.Index(
                fields=(
                    "composition",
                    "media_type",
                    "is_active",
                ),
                name="creative_media_comp_type_idx",
            ),
            models.Index(
                fields=(
                    "source_content_type",
                    "source_object_id",
                ),
                name="creative_media_source_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=(
                    Q(width__isnull=True)
                    | Q(width__gt=0)
                ),
                name="creative_media_width_valid",
            ),
            models.CheckConstraint(
                check=(
                    Q(height__isnull=True)
                    | Q(height__gt=0)
                ),
                name="creative_media_height_valid",
            ),
            models.CheckConstraint(
                check=(
                    Q(duration_ms__isnull=True)
                    | Q(duration_ms__gt=0)
                ),
                name="creative_media_duration_valid",
            ),
        ]