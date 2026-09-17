# apps/audio_catalog/models/release_artwork.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from __future__ import annotations

from django.db import models

from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_conversion import MediaConversionMixin
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

from .artwork import MusicArtwork
from .base import PublicIDTimestampedModel


class MusicReleaseArtwork(
    MediaAssetsMixin,
    MediaAutoConvertMixin,
    MediaConversionMixin,
    PublicIDTimestampedModel,
):
    IMAGE = FileUpload("audio_catalog", "artworks", "releases")

    release = models.ForeignKey(
        "audio_catalog.MusicRelease",
        on_delete=models.CASCADE,
        related_name="artworks",
    )

    role = models.CharField(
        max_length=20,
        choices=MusicArtwork.Role.choices,
        default=MusicArtwork.Role.PRIMARY,
        db_index=True,
    )
    label = models.CharField(max_length=120, blank=True, default="")

    image = models.ImageField(
        upload_to=IMAGE,
        max_length=700,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
    )

    is_converted = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_primary = models.BooleanField(default=False, db_index=True)

    primary_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    aspect_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=5,
        null=True,
        blank=True,
    )
    dominant_color = models.CharField(max_length=16, blank=True, default="")
    blurhash = models.CharField(max_length=180, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)

    media_conversion_config = {
        "image": {
            "upload": IMAGE,
            "kind": "image",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_image = getattr(self.image, "name", None)

    def _media_changed(self):
        return getattr(self.image, "name", None) != self._original_image

    def _sync_primary_slot(self):
        expected = 1 if self.is_primary and self.is_active else None
        changed = self.primary_slot != expected
        self.primary_slot = expected
        return changed

    def save(self, *args, **kwargs):
        changed = self._sync_primary_slot()

        if changed and kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = list(
                dict.fromkeys([*kwargs["update_fields"], "primary_slot"])
            )

        return super().save(*args, **kwargs)

    def is_available(self):
        return bool(self.image and self.is_active and self.is_converted)

    def can_deliver_asset(self, *, viewer, field_name, intent):
        if viewer is None or not getattr(viewer, "is_authenticated", False):
            return False

        if field_name != "image" or not self.is_available():
            return False

        if self.release.status != self.release.Status.PUBLISHED:
            return bool(getattr(viewer, "is_staff", False))

        return True

    def __str__(self) -> str:
        return f"{self.release.title} · {self.get_role_display()}"

    class Meta:
        verbose_name = "Music Release Artwork"
        verbose_name_plural = "Music Release Artworks"
        ordering = ("sort_order", "-is_primary", "id")
        indexes = [
            models.Index(
                fields=("release", "is_active", "is_primary"),
                name="audio_release_artwork_idx",
            ),
            models.Index(
                fields=("role", "is_active"),
                name="audio_rel_artwork_role_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("release", "primary_slot"),
                name="audio_one_active_primary_release_artwork",
            ),
        ]