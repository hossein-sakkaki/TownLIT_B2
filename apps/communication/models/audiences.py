# apps/communication/models/audiences.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.conf import settings
from django.db import models

from apps.communication.constants import (
    TARGET_GROUP_CHOICES,
    AudienceKind,
    AudienceMatchType,
    AudienceRuleField,
    AudienceRuleOperator,
)

from .base import CommunicationRecord, PublicCommunicationRecord


class EmailAudience(PublicCommunicationRecord):
    """
    Reusable recipient audience for campaigns.
    """

    name = models.CharField(
        max_length=140,
        unique=True,
        verbose_name="Audience Name",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    kind = models.CharField(
        max_length=20,
        choices=AudienceKind.choices,
        default=AudienceKind.DYNAMIC,
        db_index=True,
        verbose_name="Audience Type",
    )
    match_type = models.CharField(
        max_length=10,
        choices=AudienceMatchType.choices,
        default=AudienceMatchType.ALL,
        verbose_name="Rule Matching",
    )

    preset_key = models.CharField(
        max_length=50,
        choices=TARGET_GROUP_CHOICES,
        blank=True,
        default="",
        verbose_name="TownLIT Preset",
        help_text="Optional built-in audience preset.",
    )

    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="communication_audiences",
        verbose_name="Included Users",
    )
    external_contacts = models.ManyToManyField(
        "communication.ExternalContact",
        blank=True,
        related_name="communication_audiences",
        verbose_name="External Contacts",
    )

    respect_unsubscribe = models.BooleanField(
        default=True,
        verbose_name="Respect Unsubscribe Preferences",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active",
    )

    estimated_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Estimated Recipients",
    )
    last_estimated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Estimated At",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_audiences_created",
        verbose_name="Created By",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_audiences_updated",
        verbose_name="Updated By",
    )

    class Meta:
        verbose_name = "Email Audience"
        verbose_name_plural = "Email Audiences"
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=["kind", "is_active"],
                name="comm_aud_kind_active_idx",
            ),
        ]

    def __str__(self):
        return self.name


class EmailAudienceRule(CommunicationRecord):
    """
    One dynamic audience rule.
    """

    audience = models.ForeignKey(
        EmailAudience,
        on_delete=models.CASCADE,
        related_name="rules",
        verbose_name="Audience",
    )
    field = models.CharField(
        max_length=40,
        choices=AudienceRuleField.choices,
        verbose_name="Field",
    )
    operator = models.CharField(
        max_length=20,
        choices=AudienceRuleOperator.choices,
        verbose_name="Operator",
    )
    value = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Value",
    )
    negate = models.BooleanField(
        default=False,
        verbose_name="Negate Rule",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name="Sort Order",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Enabled",
    )

    class Meta:
        verbose_name = "Email Audience Rule"
        verbose_name_plural = "Email Audience Rules"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(
                fields=["audience", "sort_order"],
                name="comm_aud_rule_order_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_field_display()} "
            f"{self.get_operator_display()}"
        )