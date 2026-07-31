# apps/audio_catalog/models/catalog.py

from __future__ import annotations

from django.db import models

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel


class AudioCatalog(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    A logical collection of music tracks.
    """

    SLUG_ALLOW_UNICODE = True

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        AUTHENTICATED = "authenticated", "Authenticated"
        PUBLIC = "public", "Public"

    name = models.CharField(
        max_length=160,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.AUTHENTICATED,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    def get_slug_source(self) -> str:
        """
        Use the catalog name for its stable slug.
        """

        return self.name

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Audio Catalog"
        verbose_name_plural = "Audio Catalogs"

        ordering = [
            "sort_order",
            "name",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "is_active",
                    "visibility",
                    "sort_order",
                ]
            ),
        ]