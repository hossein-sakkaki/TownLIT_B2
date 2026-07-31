# apps/audio_catalog/models/taxonomy.py

from __future__ import annotations

from django.db import models

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel


class TaxonomyBase(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    Shared taxonomy model behavior.
    """

    SLUG_ALLOW_UNICODE = True

    name = models.CharField(
        max_length=100,
    )

    description = models.TextField(
        blank=True,
        default="",
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    def get_slug_source(self) -> str:
        """
        Use the taxonomy name for its slug.
        """

        return self.name

    def __str__(self) -> str:
        return self.name

    class Meta:
        abstract = True

        ordering = [
            "sort_order",
            "name",
            "id",
        ]


class AudioCategory(TaxonomyBase):
    icon = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    class Meta(TaxonomyBase.Meta):
        verbose_name = "Audio Category"
        verbose_name_plural = "Audio Categories"


class AudioGenre(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name = "Audio Genre"
        verbose_name_plural = "Audio Genres"


class AudioMood(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name = "Audio Mood"
        verbose_name_plural = "Audio Moods"


class AudioTag(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name = "Audio Tag"
        verbose_name_plural = "Audio Tags"