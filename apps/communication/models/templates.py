# apps/communication/models/templates.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models

from apps.communication.constants import (
    EMAIL_LAYOUT_CHOICES,
    LAYOUT_BASE_SITE,
    EmailEditorMode,
    EmailTemplateCategory,
)

from .base import CommunicationRecord, EmailContentBlockBase


class EmailTemplate(CommunicationRecord):
    """
    Reusable email template.

    Existing templates keep their original database identity.
    """

    name = models.CharField(
        max_length=120,
        unique=True,
        verbose_name="Template Name",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    category = models.CharField(
        max_length=30,
        choices=EmailTemplateCategory.choices,
        default=EmailTemplateCategory.GENERAL,
        db_index=True,
        verbose_name="Category",
    )
    editor_mode = models.CharField(
        max_length=20,
        choices=EmailEditorMode.choices,
        default=EmailEditorMode.RICH_TEXT,
        db_index=True,
        verbose_name="Editor",
    )

    layout = models.CharField(
        max_length=30,
        choices=EMAIL_LAYOUT_CHOICES,
        default=LAYOUT_BASE_SITE,
        verbose_name="Layout Template",
    )
    theme = models.ForeignKey(
        "communication.EmailTheme",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="templates",
        verbose_name="Email Theme",
    )

    subject_template = models.CharField(
        max_length=255,
        verbose_name="Email Subject",
    )
    preheader_template = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Preheader Text",
        help_text="Short preview text shown by many email clients.",
    )
    body_template = RichTextUploadingField(
        blank=True,
        verbose_name="Email Body",
    )

    default_context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Default Context",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active",
    )
    is_system = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="System Template",
        help_text="System templates are intended for transactional emails.",
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Locked",
        help_text="Locked templates require elevated care when editing.",
    )
    version = models.PositiveIntegerField(
        default=1,
        verbose_name="Version",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_templates_created",
        verbose_name="Created By",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_templates_updated",
        verbose_name="Updated By",
    )

    class Meta:
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(
                fields=["category", "is_active"],
                name="comm_tpl_cat_active_idx",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def uses_block_builder(self):
        return self.editor_mode == EmailEditorMode.BLOCKS


class EmailTemplateBlock(EmailContentBlockBase):
    """
    One reusable visual block inside a template.
    """

    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.CASCADE,
        related_name="content_blocks",
        verbose_name="Email Template",
    )

    class Meta:
        verbose_name = "Email Template Block"
        verbose_name_plural = "Email Template Blocks"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(
                fields=["template", "sort_order"],
                name="comm_tpl_block_order_idx",
            ),
        ]

    def __str__(self):
        return self.name or (
            f"{self.get_block_type_display()} #{self.sort_order}"
        )