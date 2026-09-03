# apps/subscriptions/models/event.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.subscriptions.constants import SubscriptionEventSource


class SubscriptionEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    account = models.ForeignKey(
        "subscriptions.SubscriptionAccount",
        on_delete=models.CASCADE,
        related_name="events",
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    event_type = models.CharField(max_length=80, db_index=True)
    source = models.CharField(
        max_length=20,
        choices=SubscriptionEventSource.choices,
        default=SubscriptionEventSource.SYSTEM,
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_events_performed",
    )

    dedupe_key = models.CharField(max_length=255, null=True, blank=True, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Subscription Event"
        verbose_name_plural = "Subscription Events"
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(fields=["account", "-occurred_at"]),
            models.Index(fields=["subscription", "-occurred_at"]),
            models.Index(fields=["event_type", "-occurred_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.occurred_at}"
