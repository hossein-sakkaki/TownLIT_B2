# apps/conversation/models/pins.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.conversation.constants import (
    MESSAGE_PIN_DURATION_CHOICES,
    PIN_NONE,
)

from .dialogue import Dialogue
from .message import Message


class DialoguePin(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dialogue_pins",
        verbose_name="User",
    )
    dialogue = models.ForeignKey(
        Dialogue,
        on_delete=models.CASCADE,
        related_name="pins",
        verbose_name="Dialogue",
    )
    # Stable per-user pin order: 1..5
    position = models.PositiveSmallIntegerField(verbose_name="Pin Position")
    pinned_at = models.DateTimeField(auto_now_add=True, verbose_name="Pinned At")

    class Meta:
        ordering = ["position", "-pinned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dialogue"],
                name="uq_dialogue_pin_user_dialogue",
            ),
            models.UniqueConstraint(
                fields=["user", "position"],
                name="uq_dialogue_pin_user_position",
            ),
            models.CheckConstraint(
                check=Q(position__gte=1) & Q(position__lte=5),
                name="ck_dialogue_pin_position_range",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} pinned {self.dialogue.slug} at {self.position}"


class MessagePin(models.Model):
    id = models.BigAutoField(primary_key=True)
    dialogue = models.ForeignKey(
        Dialogue,
        on_delete=models.CASCADE,
        related_name="message_pins",
        verbose_name="Dialogue",
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="pins",
        verbose_name="Message",
    )
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_pins_created",
        verbose_name="Pinned By",
    )
    # Stable shared pin order inside one dialogue: 1..5
    position = models.PositiveSmallIntegerField(verbose_name="Pin Position")
    # Optional expiry/reminder policy
    pin_duration = models.CharField(
        max_length=20,
        choices=MESSAGE_PIN_DURATION_CHOICES,
        default=PIN_NONE,
        verbose_name="Pin Duration",
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expires At")
    reminders_enabled = models.BooleanField(default=False, verbose_name="Reminders Enabled")
    reminder_interval_minutes = models.PositiveIntegerField(null=True, blank=True, verbose_name="Reminder Interval Minutes")
    next_reminder_at = models.DateTimeField(null=True, blank=True, verbose_name="Next Reminder At")
    last_reminded_at = models.DateTimeField(null=True, blank=True, verbose_name="Last Reminded At")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        ordering = ["position", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dialogue", "message"],
                name="uq_message_pin_dialogue_message",
            ),
            models.UniqueConstraint(
                fields=["dialogue", "position"],
                name="uq_message_pin_dialogue_position",
            ),
            models.CheckConstraint(
                check=Q(position__gte=1) & Q(position__lte=5),
                name="ck_message_pin_position_range",
            ),
        ]

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Pin #{self.position} in {self.dialogue.slug} for message {self.message_id}"
