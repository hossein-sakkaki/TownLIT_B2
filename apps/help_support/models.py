# apps/help_support/models.py

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.help_support.constants import (
    SUPPORT_CATEGORY_CHOICES,
    SUPPORT_CATEGORY_OTHER,
    SUPPORT_AREA_CHOICES,
    SUPPORT_AREA_GENERAL,
    SUPPORT_SOURCE_CHOICES,
    SUPPORT_SOURCE_SETTINGS,
    SUPPORT_STATUS_CHOICES,
    SUPPORT_STATUS_OPEN,
    SUPPORT_PRIORITY_CHOICES,
    SUPPORT_PRIORITY_NORMAL,
    SUPPORT_SENDER_CHOICES,
    SUPPORT_SENDER_USER,
    SUPPORT_AI_STATUS_CHOICES,
    SUPPORT_AI_NOT_USED,
)


class SupportTicket(models.Model):
    """
    Canonical TownLIT Help & Support ticket.

    This is intentionally separate from TownLIT Sanctuary:
    - Sanctuary handles safety, abuse, moderation and objectionable content.
    - Help & Support handles product, account, technical and service support.

    context_type/context_id allow future features such as Store, Orders,
    Payments or Organizations to attach a ticket to their own resource
    without coupling this app to those models.
    """

    id = models.BigAutoField(primary_key=True)

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
        db_index=True,
    )

    reply_email = models.EmailField(
        max_length=254,
        blank=True,
        default="",
    )

    category = models.CharField(
        max_length=32,
        choices=SUPPORT_CATEGORY_CHOICES,
        default=SUPPORT_CATEGORY_OTHER,
        db_index=True,
    )

    area = models.CharField(
        max_length=32,
        choices=SUPPORT_AREA_CHOICES,
        default=SUPPORT_AREA_GENERAL,
        db_index=True,
    )

    source = models.CharField(
        max_length=32,
        choices=SUPPORT_SOURCE_CHOICES,
        default=SUPPORT_SOURCE_SETTINGS,
        db_index=True,
    )

    subject = models.CharField(
        max_length=160,
    )

    status = models.CharField(
        max_length=24,
        choices=SUPPORT_STATUS_CHOICES,
        default=SUPPORT_STATUS_OPEN,
        db_index=True,
    )

    priority = models.CharField(
        max_length=16,
        choices=SUPPORT_PRIORITY_CHOICES,
        default=SUPPORT_PRIORITY_NORMAL,
        db_index=True,
    )

    context_type = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Optional logical resource type such as order, product or profile.",
    )

    context_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Optional identifier for the related resource.",
    )

    client_app_version = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )

    client_platform = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )

    ai_status = models.CharField(
        max_length=24,
        choices=SUPPORT_AI_STATUS_CHOICES,
        default=SUPPORT_AI_NOT_USED,
        db_index=True,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
        limit_choices_to={"is_staff": True},
    )

    last_message_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "priority", "-created_at"]),
            models.Index(fields=["requester", "status", "-last_message_at"]),
            models.Index(fields=["category", "area", "status"]),
            models.Index(fields=["source", "status"]),
        ]

    def __str__(self):
        return f"{self.public_id} — {self.subject}"


class SupportTicketMessage(models.Model):
    """
    Message stream belonging to a SupportTicket.

    sender_type deliberately supports user/staff/system/ai so future
    AI-assisted support can be added without redesigning ticket history.
    """

    id = models.BigAutoField(primary_key=True)

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_ticket_messages",
    )

    sender_type = models.CharField(
        max_length=16,
        choices=SUPPORT_SENDER_CHOICES,
        default=SUPPORT_SENDER_USER,
        db_index=True,
    )

    body = models.TextField()

    is_internal = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Internal messages are never exposed to the requesting user.",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        verbose_name = "Support Ticket Message"
        verbose_name_plural = "Support Ticket Messages"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["ticket", "is_internal", "created_at"]),
            models.Index(fields=["sender_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.ticket_id} — {self.sender_type} — {self.id}"