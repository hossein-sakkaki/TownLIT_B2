# apps/creative_editor/models/font.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-07-21.
# Last Update by Hossein Sakkaki on 2026-08-10.

from __future__ import annotations

import os
import re

from django.core.exceptions import ValidationError
from django.db import models

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CreativeFont(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    An approved font available to Creative Editor rendering.
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

    display_name = models.CharField(
        max_length=120,
    )

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
        default=Source.BUNDLED,
        db_index=True,
    )

    # Exact bundled binary used by every platform.
    binary_filename = models.CharField(
        max_length=180,
        blank=True,
        default="",
    )

    asset_version = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )

    asset_sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
    )

    supports_ltr = models.BooleanField(
        default=True,
    )

    supports_rtl = models.BooleanField(
        default=False,
    )

    supports_bold = models.BooleanField(
        default=False,
    )

    supports_italic = models.BooleanField(
        default=False,
    )

    #  User-selectable fonts appear in the Creative Editor picker.

    #  Hidden fallback fonts remain active for glyph resolution and
    #  rendering but are not exposed as creative style choices.
    is_user_selectable = models.BooleanField(
        default=True,
        db_index=True,
    )

    minimum_size = models.PositiveSmallIntegerField(
        default=12,
    )

    maximum_size = models.PositiveSmallIntegerField(
        default=160,
    )

    preview_text = models.CharField(
        max_length=240,
        blank=True,
        default="",
    )

    license_name = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    license_url = models.URLField(
        max_length=300,
        blank=True,
        default="",
    )

    license_reference = models.CharField(
        max_length=220,
        blank=True,
        default="",
    )

    copyright_notice = models.CharField(
        max_length=300,
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    def clean(self) -> None:
        super().clean()

        self.key = str(
            self.key or ""
        ).strip()

        self.postscript_name = str(
            self.postscript_name or ""
        ).strip()

        self.binary_filename = str(
            self.binary_filename or ""
        ).strip()

        self.asset_version = str(
            self.asset_version or ""
        ).strip()

        self.asset_sha256 = str(
            self.asset_sha256 or ""
        ).strip().lower()

        if self.binary_filename:
            if os.path.basename(
                self.binary_filename
            ) != self.binary_filename:
                raise ValidationError(
                    {
                        "binary_filename":
                            "Font filename must not contain directories."
                    }
                )

            if not self.binary_filename.lower().endswith(
                (
                    ".ttf",
                    ".otf",
                )
            ):
                raise ValidationError(
                    {
                        "binary_filename":
                            "Bundled creative fonts must be TTF or OTF."
                    }
                )

        if (
            self.asset_sha256
            and not _SHA256_RE.fullmatch(
                self.asset_sha256
            )
        ):
            raise ValidationError(
                {
                    "asset_sha256":
                        "SHA-256 must contain exactly 64 hexadecimal characters."
                }
            )

        if self.source == self.Source.BUNDLED:
            missing = {}

            if not self.binary_filename:
                missing["binary_filename"] = (
                    "Bundled fonts require a binary filename."
                )

            if not self.postscript_name:
                missing["postscript_name"] = (
                    "Bundled fonts require a PostScript name."
                )

            if not self.asset_sha256:
                missing["asset_sha256"] = (
                    "Bundled fonts require a SHA-256 checksum."
                )

            if not self.license_name:
                missing["license_name"] = (
                    "Bundled fonts require license information."
                )

            if missing:
                raise ValidationError(
                    missing
                )

    def get_slug_source(self) -> str:
        return self.key or self.display_name

    def __str__(self) -> str:
        return self.display_name

    class Meta:
        verbose_name = "Creative Font"
        verbose_name_plural = "Creative Fonts"

        ordering = (
            "sort_order",
            "display_name",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "is_active",
                    "is_user_selectable",
                    "sort_order",
                ),
                name="creative_font_picker_idx",
            ),
            models.Index(
                fields=(
                    "is_active",
                    "category",
                    "sort_order",
                ),
                name="creative_font_active_cat_idx",
            ),
            models.Index(
                fields=(
                    "source",
                    "is_active",
                ),
                name="creative_font_source_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    maximum_size__gte=models.F(
                        "minimum_size"
                    )
                ),
                name="creative_font_size_range_valid",
            ),
        ]