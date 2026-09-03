# apps/subscriptions/models/plan.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.subscriptions.constants import BillingInterval
from common.reference_data.currencies import CURRENCY_CHOICES, USD


class SubscriptionPlan(models.Model):
    id = models.BigAutoField(primary_key=True)
    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    audience_key = models.SlugField(max_length=80, db_index=True)
    description = models.TextField(blank=True)

    trial_key = models.SlugField(max_length=80, null=True, blank=True, db_index=True)
    trial_duration_days = models.PositiveSmallIntegerField(default=0)

    is_public = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        ordering = ("sort_order", "name", "id")
        indexes = [
            models.Index(fields=["audience_key", "is_active", "is_public"]),
        ]

    def clean(self):
        super().clean()
        if self.trial_duration_days > 0 and not self.trial_key:
            raise ValidationError({
                "trial_key": "Plans with a trial duration require a trial key."
            })

    def __str__(self):
        return self.name


class SubscriptionPlanPrice(models.Model):
    id = models.BigAutoField(primary_key=True)
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name="prices",
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=USD,
        db_index=True,
    )
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    provider_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    provider_price_reference = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    valid_from = models.DateTimeField(default=timezone.now, db_index=True)
    valid_until = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription Plan Price"
        verbose_name_plural = "Subscription Plan Prices"
        ordering = ("plan_id", "currency", "billing_interval", "-valid_from")
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gte=0),
                name="subscriptions_plan_price_amount_non_negative",
            ),
            models.CheckConstraint(
                check=Q(valid_until__isnull=True) | Q(valid_until__gt=models.F("valid_from")),
                name="subscriptions_plan_price_valid_window",
            ),
            models.UniqueConstraint(
                fields=["plan", "currency", "billing_interval", "valid_from"],
                name="subscriptions_unique_plan_price_version",
            ),
        ]
        indexes = [
            models.Index(fields=["plan", "currency", "billing_interval", "is_active"]),
        ]

    def clean(self):
        super().clean()
        if self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "Valid until must be after valid from."})

    def __str__(self):
        return f"{self.plan.key}:{self.currency}:{self.billing_interval}:{self.amount}"
