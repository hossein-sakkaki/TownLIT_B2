# apps/creative_editor/models/background.py

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from utils.mixins.slug_mixin import SlugMixin

from .base import PublicIDTimestampedModel


class CreativeBackgroundPreset(
    SlugMixin,
    PublicIDTimestampedModel,
):
    """
    One server-managed creative editor background preset.
    """

    SLUG_ALLOW_UNICODE = False

    class BackgroundType(models.TextChoices):
        COLOR = "color", "Solid Color"
        GRADIENT = "gradient", "Gradient"

    class Consumer(models.TextChoices):
        JOURNEY = "journey", "Journey"
        MOMENT = "moment", "Moment"
        TESTIMONY = "testimony", "Testimony"
        PROFILE = "profile", "Profile"
        ANNOUNCEMENT = "announcement", "Announcement"
        CUSTOM = "custom", "Custom"

    key = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
    )

    title = models.CharField(
        max_length=120,
    )

    description = models.CharField(
        max_length=240,
        blank=True,
        default="",
    )

    background_type = models.CharField(
        max_length=20,
        choices=BackgroundType.choices,
        db_index=True,
    )

    # Used only for solid backgrounds.
    color = models.CharField(
        max_length=9,
        blank=True,
        default="",
    )

    # Used only for gradient backgrounds.
    colors = models.JSONField(
        default=list,
        blank=True,
    )

    angle = models.FloatField(
        default=90.0,
    )

    # Empty means available to every creative consumer.
    supported_consumers = models.JSONField(
        default=list,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )

    def get_slug_source(self) -> str:
        return self.key or self.title

    def clean(self):
        super().clean()

        self.key = str(
            self.key or ""
        ).strip().lower()

        self.title = str(
            self.title or ""
        ).strip()

        self.description = str(
            self.description or ""
        ).strip()

        self.color = self._normalize_hex(
            self.color,
            allow_empty=True,
        )

        self.colors = [
            self._normalize_hex(value)
            for value in (
                self.colors
                if isinstance(self.colors, list)
                else []
            )
        ]

        self.supported_consumers = (
            self._normalize_consumers(
                self.supported_consumers
            )
        )

        self._validate_background_payload()

    def _validate_background_payload(self) -> None:
        if self.background_type == self.BackgroundType.COLOR:
            if not self.color:
                raise ValidationError(
                    {
                        "color": (
                            "Solid backgrounds require one RGBA color."
                        ),
                    }
                )

            if self.colors:
                raise ValidationError(
                    {
                        "colors": (
                            "Solid backgrounds cannot define gradient colors."
                        ),
                    }
                )

            return

        if self.background_type == self.BackgroundType.GRADIENT:
            if len(self.colors) < 2:
                raise ValidationError(
                    {
                        "colors": (
                            "Gradient backgrounds require at least two colors."
                        ),
                    }
                )

            if len(self.colors) > 5:
                raise ValidationError(
                    {
                        "colors": (
                            "Gradient backgrounds cannot exceed five colors."
                        ),
                    }
                )

            if self.color:
                raise ValidationError(
                    {
                        "color": (
                            "Gradient backgrounds cannot define a solid color."
                        ),
                    }
                )

            if not -360 <= float(self.angle) <= 360:
                raise ValidationError(
                    {
                        "angle": (
                            "Gradient angle must be between -360 and 360."
                        ),
                    }
                )

            return

        raise ValidationError(
            {
                "background_type": (
                    "Unsupported creative background type."
                ),
            }
        )

    @classmethod
    def _normalize_hex(
        cls,
        value,
        *,
        allow_empty: bool = False,
    ) -> str:
        cleaned = (
            str(value or "")
            .strip()
            .replace("#", "")
            .upper()
        )

        if not cleaned and allow_empty:
            return ""

        if len(cleaned) == 6:
            cleaned = f"{cleaned}FF"

        if len(cleaned) != 8:
            raise ValidationError(
                "Colors must use #RRGGBB or #RRGGBBAA."
            )

        try:
            int(cleaned, 16)
        except ValueError as exc:
            raise ValidationError(
                "Color contains invalid hexadecimal characters."
            ) from exc

        return f"#{cleaned}"

    @classmethod
    def _normalize_consumers(
        cls,
        values,
    ) -> list[str]:
        if not isinstance(values, list):
            raise ValidationError(
                {
                    "supported_consumers": (
                        "Supported consumers must be a list."
                    ),
                }
            )

        allowed = {
            value
            for value, _ in cls.Consumer.choices
        }

        normalized: list[str] = []

        for value in values:
            candidate = str(
                value or ""
            ).strip().lower()

            if not candidate:
                continue

            if candidate not in allowed:
                raise ValidationError(
                    {
                        "supported_consumers": (
                            f"Unsupported creative consumer: {candidate}"
                        ),
                    }
                )

            if candidate not in normalized:
                normalized.append(candidate)

        return normalized

    def supports_consumer(
        self,
        consumer: str,
    ) -> bool:
        normalized_consumer = str(
            consumer or ""
        ).strip().lower()

        if not self.supported_consumers:
            return True

        return (
            normalized_consumer
            in self.supported_consumers
        )

    def as_document_background(self) -> dict:
        if self.background_type == self.BackgroundType.COLOR:
            return {
                "type": "color",
                "color": self.color,
            }

        return {
            "type": "gradient",
            "colors": list(self.colors),
            "angle": float(self.angle),
        }

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Creative Background Preset"
        verbose_name_plural = "Creative Background Presets"
        ordering = (
            "sort_order",
            "title",
            "id",
        )

        indexes = [
            models.Index(
                fields=(
                    "is_active",
                    "is_featured",
                    "sort_order",
                ),
                name="creative_bg_active_feature_idx",
            ),
            models.Index(
                fields=(
                    "background_type",
                    "is_active",
                ),
                name="creative_bg_type_active_idx",
            ),
        ]