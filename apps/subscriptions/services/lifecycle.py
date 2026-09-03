# apps/subscriptions/services/lifecycle.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.subscriptions.constants import (
    CURRENT_SUBSCRIPTION_STATUSES,
    SubscriptionEventSource,
    SubscriptionStatus,
)
from apps.subscriptions.models import (
    Subscription,
    SubscriptionAccount,
    SubscriptionEvent,
    SubscriptionTrialUsage,
)


def _ensure_account_can_subscribe(account: SubscriptionAccount):
    if account.status != "active":
        raise ValidationError("Subscription account is not active.")


def _ensure_no_current_subscription(account: SubscriptionAccount):
    if account.subscriptions.filter(status__in=CURRENT_SUBSCRIPTION_STATUSES).exists():
        raise ValidationError("Subscription account already has a current subscription.")


@transaction.atomic
def start_trial(*, account, plan, billing_interval, actor=None, now=None):
    now = now or timezone.now()
    account = SubscriptionAccount.objects.select_for_update().get(pk=account.pk)

    _ensure_account_can_subscribe(account)
    _ensure_no_current_subscription(account)

    if not plan.is_active:
        raise ValidationError("Subscription plan is not active.")

    if plan.trial_duration_days <= 0 or not plan.trial_key:
        raise ValidationError("Subscription plan does not provide a trial period.")

    if SubscriptionTrialUsage.objects.filter(
        account=account,
        trial_key=plan.trial_key,
    ).exists():
        raise ValidationError("This subscription account has already used this trial.")

    trial_ends_at = now + timedelta(days=plan.trial_duration_days)

    subscription = Subscription(
        account=account,
        plan=plan,
        status=SubscriptionStatus.TRIALING,
        billing_interval=billing_interval,
        trial_started_at=now,
        trial_ends_at=trial_ends_at,
    )
    subscription.full_clean()
    subscription.save()

    SubscriptionTrialUsage.objects.create(
        account=account,
        trial_key=plan.trial_key,
        subscription=subscription,
        started_at=now,
        ends_at=trial_ends_at,
    )

    SubscriptionEvent.objects.create(
        account=account,
        subscription=subscription,
        event_type="trial_started",
        source=SubscriptionEventSource.SERVICE,
        actor=actor,
        payload={
            "plan_key": plan.key,
            "billing_interval": billing_interval,
            "trial_key": plan.trial_key,
            "trial_duration_days": plan.trial_duration_days,
        },
    )

    return subscription


@transaction.atomic
def activate_subscription(
    *,
    account,
    plan,
    billing_interval,
    period_started_at,
    period_ends_at,
    provider_key=None,
    provider_subscription_reference=None,
    actor=None,
):
    account = SubscriptionAccount.objects.select_for_update().get(pk=account.pk)

    _ensure_account_can_subscribe(account)

    current = (
        account.subscriptions
        .select_for_update()
        .filter(status__in=CURRENT_SUBSCRIPTION_STATUSES)
        .first()
    )

    if current and current.plan_id != plan.id:
        raise ValidationError("Subscription account already has a different current subscription.")

    if current:
        subscription = current
        subscription.plan = plan
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.billing_interval = billing_interval
        subscription.current_period_started_at = period_started_at
        subscription.current_period_ends_at = period_ends_at
        subscription.provider_key = provider_key or subscription.provider_key
        subscription.provider_subscription_reference = (
            provider_subscription_reference
            or subscription.provider_subscription_reference
        )
        subscription.cancel_at_period_end = False
        subscription.cancel_requested_at = None
        subscription.canceled_at = None
        subscription.ended_at = None
        subscription.full_clean()
        subscription.save()
    else:
        subscription = Subscription(
            account=account,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            billing_interval=billing_interval,
            provider_key=provider_key,
            provider_subscription_reference=provider_subscription_reference,
            current_period_started_at=period_started_at,
            current_period_ends_at=period_ends_at,
        )
        subscription.full_clean()
        subscription.save()

    SubscriptionEvent.objects.create(
        account=account,
        subscription=subscription,
        event_type="subscription_activated",
        source=SubscriptionEventSource.SERVICE,
        actor=actor,
        payload={
            "plan_key": plan.key,
            "billing_interval": billing_interval,
        },
    )

    return subscription


@transaction.atomic
def cancel_subscription(*, subscription, immediately=False, actor=None, now=None):
    now = now or timezone.now()
    subscription = Subscription.objects.select_for_update().select_related("account").get(
        pk=subscription.pk
    )

    if subscription.status not in CURRENT_SUBSCRIPTION_STATUSES:
        return subscription

    if immediately:
        subscription.status = SubscriptionStatus.CANCELED
        subscription.cancel_at_period_end = False
        subscription.cancel_requested_at = now
        subscription.canceled_at = now
        subscription.ended_at = now
        event_type = "subscription_canceled_immediately"
    else:
        subscription.cancel_at_period_end = True
        subscription.cancel_requested_at = now
        event_type = "subscription_cancel_scheduled"

    subscription.save(
        update_fields=[
            "status",
            "cancel_at_period_end",
            "cancel_requested_at",
            "canceled_at",
            "ended_at",
            "updated_at",
        ]
    )

    SubscriptionEvent.objects.create(
        account=subscription.account,
        subscription=subscription,
        event_type=event_type,
        source=SubscriptionEventSource.SERVICE,
        actor=actor,
    )

    return subscription
