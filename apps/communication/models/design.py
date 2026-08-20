# apps/communication/models/design.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.communication.constants import (
    EMAIL_LAYOUT_CHOICES,
    LAYOUT_BASE_SITE,
)

from .base import PublicCommunicationRecord


class EmailTheme(PublicCommunicationRecord):
    """
    Reusable visual theme for campaign emails.
    """

    name = models.CharField(
        max_length=120,
        unique=True,
        verbose_name="Theme Name",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    layout = models.CharField(
        max_length=30,
        choices=EMAIL_LAYOUT_CHOICES,
        default=LAYOUT_BASE_SITE,
        verbose_name="Base Layout",
    )

    logo_url = models.URLField(
        blank=True,
        verbose_name="Logo URL",
    )

    background_color = models.CharField(
        max_length=20,
        default="#000000",
        verbose_name="Background Color",
    )
    surface_color = models.CharField(
        max_length=20,
        default="#F9F8F4",
        verbose_name="Content Background",
    )
    text_color = models.CharField(
        max_length=20,
        default="#2B2C30",
        verbose_name="Text Color",
    )
    heading_color = models.CharField(
        max_length=20,
        default="#0F52BA",
        verbose_name="Heading Color",
    )
    accent_color = models.CharField(
        max_length=20,
        default="#0F52BA",
        verbose_name="Accent Color",
    )
    secondary_accent_color = models.CharField(
        max_length=20,
        default="#F6C860",
        verbose_name="Secondary Accent",
    )
    muted_color = models.CharField(
        max_length=20,
        default="#7A7A7A",
        verbose_name="Muted Text Color",
    )
    button_text_color = models.CharField(
        max_length=20,
        default="#FFFFFF",
        verbose_name="Button Text Color",
    )

    font_family = models.CharField(
        max_length=255,
        default="Lato, Noto Sans, Helvetica, Segoe UI, sans-serif",
        verbose_name="Font Stack",
    )
    content_width = models.PositiveSmallIntegerField(
        default=600,
        validators=[
            MinValueValidator(320),
            MaxValueValidator(720),
        ],
        verbose_name="Content Width",
    )
    border_radius = models.PositiveSmallIntegerField(
        default=10,
        validators=[MaxValueValidator(40)],
        verbose_name="Border Radius",
    )

    style_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Advanced Style Configuration",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active",
    )
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Default Theme",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_themes_created",
        verbose_name="Created By",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_themes_updated",
        verbose_name="Updated By",
    )

    class Meta:
        verbose_name = "Email Theme"
        verbose_name_plural = "Email Themes"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.is_default:
            type(self).objects.exclude(pk=self.pk).filter(
                is_default=True
            ).update(is_default=False)

    def __str__(self):
        return self.name