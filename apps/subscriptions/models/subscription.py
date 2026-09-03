# apps/subscriptions/models/subscription.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.subscriptions.constants import (
    BillingInterval,
    CURRENT_SUBSCRIPTION_STATUSES,
    SubscriptionStatus,
)


class Subscription(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    account = models.ForeignKey(
        "subscriptions.SubscriptionAccount",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan",
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )

    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        db_index=True,
    )

    # MySQL-safe uniqueness slot for the current subscription.
    current_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        db_index=True,
    )

    provider_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    provider_subscription_reference = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    trial_started_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True, db_index=True)

    current_period_started_at = models.DateTimeField(null=True, blank=True)
    current_period_ends_at = models.DateTimeField(null=True, blank=True, db_index=True)

    cancel_at_period_end = models.BooleanField(default=False)
    cancel_requested_at = models.DateTimeField(null=True, blank=True, db_index=True)
    canceled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "account",
                    "current_slot",
                ],
                name="subscriptions_one_current_subscription_per_account",
            ),
            models.CheckConstraint(
                check=(
                    Q(trial_started_at__isnull=True)
                    | Q(trial_ends_at__isnull=True)
                    | Q(trial_ends_at__gt=models.F("trial_started_at"))
                ),
                name="subscriptions_valid_trial_window",
            ),
            models.CheckConstraint(
                check=(
                    Q(current_period_started_at__isnull=True)
                    | Q(current_period_ends_at__isnull=True)
                    | Q(current_period_ends_at__gt=models.F("current_period_started_at"))
                ),
                name="subscriptions_valid_current_period_window",
            ),
        ]
        indexes = [
            models.Index(fields=["account", "status"]),
            models.Index(fields=["plan", "status"]),
            models.Index(fields=["provider_key", "provider_subscription_reference"]),
        ]

    def _sync_current_slot(self):
        self.current_slot = (
            1
            if self.status in CURRENT_SUBSCRIPTION_STATUSES
            else None
        )

    def clean(self):
        super().clean()
        self._sync_current_slot()

        if self.status == SubscriptionStatus.TRIALING:
            if not self.trial_started_at or not self.trial_ends_at:
                raise ValidationError("Trialing subscriptions require a trial window.")

        if self.trial_started_at and self.trial_ends_at:
            if self.trial_ends_at <= self.trial_started_at:
                raise ValidationError({"trial_ends_at": "Trial end must be after trial start."})

        if self.current_period_started_at and self.current_period_ends_at:
            if self.current_period_ends_at <= self.current_period_started_at:
                raise ValidationError({
                    "current_period_ends_at": "Current period end must be after its start."
                })

    def save(self, *args, **kwargs):
        self._sync_current_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("current_slot")
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Subscription({self.public_id}) {self.plan.key}:{self.status}"
