# apps/audio_catalog/models/variant.py

from __future__ import annotations

from django.db import models
from django.db.models import Q

from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_conversion import MediaConversionMixin

from validators.mediaValidators.audio_validators import (
    validate_audio_file,
)
from validators.security_validators import (
    validate_no_executable_file,
)

from .base import PublicIDTimestampedModel


class MusicTrackVariant(
    MediaAssetsMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    PublicIDTimestampedModel,
):
    """
    One playable or source variant of a music track.
    """

    # -------------------------------------------------
    # Upload roots
    # -------------------------------------------------
    AUDIO = FileUpload(
        "audio_catalog",
        "audios",
        "tracks",
    )

    WAVEFORM = FileUpload(
        "audio_catalog",
        "waveforms",
        "tracks",
    )

    # -------------------------------------------------
    # Variant types
    # -------------------------------------------------
    class VariantType(models.TextChoices):
        MASTER = "master", "Master"
        PLAYBACK = "playback", "Playback"
        PREVIEW = "preview", "Preview"
        CLIP = "clip", "Clip"
        LOOP = "loop", "Loop"
        STEM = "stem", "Stem"
        INSTRUMENTAL = "instrumental", "Instrumental"
        ALTERNATE = "alternate", "Alternate"

    # -------------------------------------------------
    # Relations
    # -------------------------------------------------
    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="variants",
    )

    # -------------------------------------------------
    # Identity
    # -------------------------------------------------
    variant_type = models.CharField(
        max_length=24,
        choices=VariantType.choices,
        db_index=True,
    )

    label = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    locale = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    # -------------------------------------------------
    # Media
    # -------------------------------------------------
    audio_file = models.FileField(
        upload_to=AUDIO.dir_upload,
        max_length=700,
        validators=[
            validate_audio_file,
            validate_no_executable_file,
        ],
    )

    waveform_file = models.FileField(
        upload_to=WAVEFORM.dir_upload,
        max_length=700,
        blank=True,
        validators=[
            validate_no_executable_file,
        ],
    )

    is_converted = models.BooleanField(
        default=False,
        db_index=True,
    )

    # -------------------------------------------------
    # Availability and delivery
    # -------------------------------------------------
    is_default = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_streamable = models.BooleanField(
        default=True,
    )

    is_downloadable = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    # -------------------------------------------------
    # Technical metadata
    # -------------------------------------------------
    mime_type = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    codec = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )

    container = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    bitrate_kbps = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    sample_rate_hz = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    channels = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    duration_ms = models.PositiveIntegerField(
        default=1,
    )

    source_start_ms = models.PositiveIntegerField(
        default=0,
    )

    source_end_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    file_size_bytes = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    checksum_sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    # -------------------------------------------------
    # Media conversion
    # -------------------------------------------------
    media_conversion_config = {
        "audio_file": {
            "upload": AUDIO,
            "kind": "audio",
        },
    }

    # -------------------------------------------------
    # Change tracking
    # -------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._original_audio_file = getattr(
            self.audio_file,
            "name",
            None,
        )

    def _media_changed(self) -> bool:
        """
        Detect audio replacement.
        """

        return (
            getattr(
                self.audio_file,
                "name",
                None,
            )
            != self._original_audio_file
        )

    # -------------------------------------------------
    # Availability
    # -------------------------------------------------
    def is_available(self) -> bool:
        """
        Variant is available after conversion.
        """

        return bool(
            self.audio_file
            and self.is_active
            and self.is_converted
        )

    # -------------------------------------------------
    # Asset delivery
    # -------------------------------------------------
    def can_deliver_asset(
        self,
        *,
        viewer,
        field_name: str,
        intent: str,
    ) -> bool:
        """
        Authorize variant delivery.
        """

        if (
            viewer is None
            or not getattr(
                viewer,
                "is_authenticated",
                False,
            )
        ):
            return False

        if field_name not in {
            "audio_file",
            "waveform_file",
        }:
            return False

        if not self.is_available():
            return False

        if (
            field_name == "audio_file"
            and not self.is_streamable
        ):
            return False

        if (
            intent == "download"
            and not self.is_downloadable
        ):
            return False

        if self.track.is_test_asset:
            return bool(
                getattr(
                    viewer,
                    "is_staff",
                    False,
                )
            )

        if (
            self.track.status
            != self.track.Status.PUBLISHED
        ):
            return False

        if not self.track.allow_streaming:
            return False

        return True

    def __str__(self) -> str:
        return (
            f"{self.track.title} · "
            f"{self.label or self.get_variant_type_display()}"
        )

    class Meta:
        verbose_name = "Music Track Variant"
        verbose_name_plural = "Music Track Variants"

        ordering = [
            "sort_order",
            "variant_type",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "track",
                    "is_active",
                    "is_converted",
                ]
            ),
            models.Index(
                fields=[
                    "track",
                    "is_default",
                    "is_converted",
                ]
            ),
            models.Index(
                fields=[
                    "variant_type",
                    "is_active",
                    "is_converted",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(
                    duration_ms__gt=0,
                ),
                name="audio_variant_duration_gt_zero",
            ),
            models.CheckConstraint(
                check=(
                    Q(source_end_ms__isnull=True)
                    | Q(
                        source_end_ms__gt=models.F(
                            "source_start_ms"
                        )
                    )
                ),
                name="audio_variant_source_range_valid",
            ),
            models.UniqueConstraint(
                fields=[
                    "track",
                    "variant_type",
                    "label",
                    "locale",
                ],
                name="audio_unique_track_variant_identity",
            ),
            models.UniqueConstraint(
                fields=["track"],
                condition=Q(
                    is_default=True,
                    is_active=True,
                ),
                name="audio_one_active_default_variant",
            ),
        ]