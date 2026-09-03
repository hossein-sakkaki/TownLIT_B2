# apps/subscriptions/constants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.db import models


class SubscriptionAccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    CLOSED = "closed", "Closed"


class BillingInterval(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    YEARLY = "yearly", "Yearly"


class SubscriptionStatus(models.TextChoices):
    TRIALING = "trialing", "Trialing"
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past Due"
    PAUSED = "paused", "Paused"
    CANCELED = "canceled", "Canceled"
    EXPIRED = "expired", "Expired"


CURRENT_SUBSCRIPTION_STATUSES = (
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.PAST_DUE,
    SubscriptionStatus.PAUSED,
)


class EntitlementValueType(models.TextChoices):
    BOOLEAN = "boolean", "Boolean"
    INTEGER = "integer", "Integer"
    DECIMAL = "decimal", "Decimal"
    STRING = "string", "String"
    JSON = "json", "JSON"


class EntitlementGrantSource(models.TextChoices):
    ADMIN = "admin", "TownLIT Admin"
    PROMOTION = "promotion", "Promotion"
    SYSTEM = "system", "System"
    SUPPORT = "support", "Support"


class SubscriptionEventSource(models.TextChoices):
    ADMIN = "admin", "TownLIT Admin"
    PROVIDER = "provider", "Payment Provider"
    SERVICE = "service", "TownLIT Service"
    SYSTEM = "system", "System"
