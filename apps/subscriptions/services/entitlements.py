# apps/subscriptions/services/entitlements.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.db import models
from django.utils import timezone

from apps.subscriptions.constants import CURRENT_SUBSCRIPTION_STATUSES
from apps.subscriptions.models import EntitlementDefinition, EntitlementGrant


def get_entitlement_value(*, account, key, now=None):
    now = now or timezone.now()

    entitlement = EntitlementDefinition.objects.filter(
        key=key,
        is_active=True,
    ).first()

    if not entitlement:
        return None

    override = (
        EntitlementGrant.objects
        .filter(
            account=account,
            entitlement=entitlement,
            is_active=True,
            revoked_at__isnull=True,
            starts_at__lte=now,
        )
        .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now))
        .order_by("-priority", "-created_at", "-id")
        .first()
    )

    if override:
        return override.value

    subscription = (
        account.subscriptions
        .filter(status__in=CURRENT_SUBSCRIPTION_STATUSES)
        .select_related("plan")
        .prefetch_related("plan__plan_entitlements__entitlement")
        .first()
    )

    if subscription:
        plan_entitlement = next(
            (
                item
                for item in subscription.plan.plan_entitlements.all()
                if item.entitlement_id == entitlement.id
            ),
            None,
        )
        if plan_entitlement:
            return plan_entitlement.value

    return entitlement.default_value


def has_entitlement(*, account, key, now=None):
    return bool(get_entitlement_value(account=account, key=key, now=now))


def get_effective_entitlements(*, account, now=None):
    now = now or timezone.now()
    definitions = EntitlementDefinition.objects.filter(is_active=True).only(
        "id",
        "key",
        "default_value",
    )

    return {
        definition.key: get_entitlement_value(
            account=account,
            key=definition.key,
            now=now,
        )
        for definition in definitions
    }
