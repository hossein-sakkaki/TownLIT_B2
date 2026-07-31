# apps/audio_catalog/models/artwork.py

from __future__ import annotations

from django.db import models
from django.db.models import Q

from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_conversion import MediaConversionMixin

from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import (
    validate_no_executable_file,
)

from .base import PublicIDTimestampedModel


class MusicArtwork(
    MediaAssetsMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    PublicIDTimestampedModel,
):
    """
    Artwork attached to one music track.
    """

    # -------------------------------------------------
    # Upload roots
    # -------------------------------------------------
    IMAGE = FileUpload(
        "audio_catalog",
        "artworks",
        "tracks",
    )

    # -------------------------------------------------
    # Roles
    # -------------------------------------------------
    class Role(models.TextChoices):
        PRIMARY = "primary", "Primary"
        THUMBNAIL = "thumbnail", "Thumbnail"
        PLAYER = "player", "Player"
        BACKGROUND = "background", "Background"
        ALTERNATE = "alternate", "Alternate"

    # -------------------------------------------------
    # Relations
    # -------------------------------------------------
    track = models.ForeignKey(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="artworks",
    )

    # -------------------------------------------------
    # Identity
    # -------------------------------------------------
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PRIMARY,
        db_index=True,
    )

    label = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    # -------------------------------------------------
    # Media
    # -------------------------------------------------
    image = models.ImageField(
        upload_to=IMAGE.dir_upload,
        max_length=700,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )

    is_converted = models.BooleanField(
        default=False,
        db_index=True,
    )

    # -------------------------------------------------
    # State
    # -------------------------------------------------
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    is_primary = models.BooleanField(
        default=False,
        db_index=True,
    )

    # -------------------------------------------------
    # Presentation metadata
    # -------------------------------------------------
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    height = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    aspect_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=5,
        null=True,
        blank=True,
    )

    dominant_color = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    blurhash = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    # -------------------------------------------------
    # Media conversion
    # -------------------------------------------------
    media_conversion_config = {
        "image": {
            "upload": IMAGE,
            "kind": "image",
        },
    }

    # -------------------------------------------------
    # Change tracking
    # -------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._original_image = getattr(
            self.image,
            "name",
            None,
        )

    def _media_changed(self) -> bool:
        """
        Detect artwork replacement.
        """

        return (
            getattr(
                self.image,
                "name",
                None,
            )
            != self._original_image
        )

    # -------------------------------------------------
    # Availability
    # -------------------------------------------------
    def is_available(self) -> bool:
        """
        Artwork is available after conversion.
        """

        return bool(
            self.image
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
        Authorize artwork delivery.
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

        if field_name != "image":
            return False

        if not self.is_available():
            return False

        if self.track.is_test_asset:
            return bool(
                getattr(
                    viewer,
                    "is_staff",
                    False,
                )
            )

        return (
            self.track.status
            == self.track.Status.PUBLISHED
        )

    def __str__(self) -> str:
        return (
            f"{self.track.title} · "
            f"{self.get_role_display()}"
        )

    class Meta:
        verbose_name = "Music Artwork"
        verbose_name_plural = "Music Artworks"

        ordering = [
            "sort_order",
            "-is_primary",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "track",
                    "is_active",
                    "is_primary",
                ]
            ),
            models.Index(
                fields=[
                    "role",
                    "is_active",
                ]
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["track"],
                condition=Q(
                    is_primary=True,
                    is_active=True,
                ),
                name="audio_one_active_primary_artwork",
            ),
        ]