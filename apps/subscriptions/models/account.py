# apps/subscriptions/models/account.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

import uuid

from django.db import models

from apps.subscriptions.constants import SubscriptionAccountStatus
from common.reference_data.currencies import CURRENCY_CHOICES, USD


class SubscriptionAccount(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    status = models.CharField(
        max_length=20,
        choices=SubscriptionAccountStatus.choices,
        default=SubscriptionAccountStatus.ACTIVE,
        db_index=True,
    )
    default_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=USD,
    )
    billing_email = models.EmailField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "Subscription Account"
        verbose_name_plural = "Subscription Accounts"
        ordering = ("-created_at",)

    def __str__(self):
        return f"SubscriptionAccount({self.public_id})"
