# apps/subscriptions/urls.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.subscriptions.views import (
    OrganizationSubscriptionOverviewView,
    SubscriptionPlanViewSet,
)


router = DefaultRouter()
router.register(
    r"plans",
    SubscriptionPlanViewSet,
    basename="subscription-plan",
)


urlpatterns = [
    path(
        "organizations/<slug:slug>/overview/",
        OrganizationSubscriptionOverviewView.as_view(),
        name="organization-subscription-overview",
    ),
]

urlpatterns += router.urls
