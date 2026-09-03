# apps/subscriptions/views/plans.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.subscriptions.selectors.plans import public_plan_queryset
from apps.subscriptions.serializers import SubscriptionPlanSerializer


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    lookup_field = "key"

    def get_queryset(self):
        return public_plan_queryset(
            audience_key=self.request.query_params.get("audience"),
        )
