# apps/creative_editor/models/font.py

from __future__ import annotations

from django.db import models

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel


class CreativeFont(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    An approved font available to creative editors.
    """

    SLUG_ALLOW_UNICODE = False

    class Category(models.TextChoices):
        SANS_SERIF = "sans_serif", "Sans Serif"
        SERIF = "serif", "Serif"
        DISPLAY = "display", "Display"
        HANDWRITING = "handwriting", "Handwriting"
        MONOSPACE = "monospace", "Monospace"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        SYSTEM = "system", "System"
        BUNDLED = "bundled", "Bundled"
        LICENSED = "licensed", "Licensed"
        OTHER = "other", "Other"

    key = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
    )
    display_name = models.CharField(max_length=120)
    postscript_name = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )
    category = models.CharField(
        max_length=24,
        choices=Category.choices,
        default=Category.SANS_SERIF,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SYSTEM,
        db_index=True,
    )
    supports_ltr = models.BooleanField(default=True)
    supports_rtl = models.BooleanField(default=False)
    supports_bold = models.BooleanField(default=True)
    supports_italic = models.BooleanField(default=False)
    minimum_size = models.PositiveSmallIntegerField(default=12)
    maximum_size = models.PositiveSmallIntegerField(default=160)
    preview_text = models.CharField(
        max_length=240,
        blank=True,
        default="",
    )
    license_reference = models.CharField(
        max_length=220,
        blank=True,
        default="",
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    def get_slug_source(self) -> str:
        return self.key or self.display_name

    def __str__(self) -> str:
        return self.display_name

    class Meta:
        verbose_name = "Creative Font"
        verbose_name_plural = "Creative Fonts"
        ordering = ("sort_order", "display_name", "id")

        indexes = [
            models.Index(
                fields=("is_active", "category", "sort_order"),
                name="creative_font_active_cat_idx",
            ),
            models.Index(
                fields=("source", "is_active"),
                name="creative_font_source_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    maximum_size__gte=models.F("minimum_size")
                ),
                name="creative_font_size_range_valid",
            ),
        ]