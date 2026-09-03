# apps/subscriptions/selectors/plans.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from apps.subscriptions.models import SubscriptionPlan


def public_plan_queryset(*, audience_key=None):
    queryset = (
        SubscriptionPlan.objects
        .filter(is_active=True, is_public=True)
        .prefetch_related(
            "plan_entitlements__entitlement",
            "prices",
        )
        .order_by("sort_order", "name", "id")
    )

    if audience_key:
        queryset = queryset.filter(audience_key=audience_key)

    return queryset
