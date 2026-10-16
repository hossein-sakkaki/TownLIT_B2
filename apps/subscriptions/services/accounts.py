# apps/subscriptions/services/accounts.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from django.db import transaction

from apps.subscriptions.constants import SubscriptionEventSource
from apps.subscriptions.models import SubscriptionAccount, SubscriptionEvent


@transaction.atomic
def update_subscription_billing_email(
    *,
    account: SubscriptionAccount,
    billing_email,
    actor=None,
):
    account = (
        SubscriptionAccount.objects
        .select_for_update()
        .get(pk=account.pk)
    )

    normalized_email = str(billing_email or "").strip()
    normalized_email = normalized_email or None

    if account.billing_email == normalized_email:
        return account

    previous_email = account.billing_email
    account.billing_email = normalized_email
    account.full_clean()
    account.save(
        update_fields=[
            "billing_email",
            "updated_at",
        ]
    )

    SubscriptionEvent.objects.create(
        account=account,
        event_type="billing_profile_updated",
        source=SubscriptionEventSource.SERVICE,
        actor=actor,
        payload={
            "field": "billing_email",
            "had_previous_value": bool(previous_email),
            "has_new_value": bool(normalized_email),
        },
    )

    return account
