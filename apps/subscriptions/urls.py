# apps/subscriptions/urls.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from rest_framework.routers import DefaultRouter

from apps.subscriptions.views.plans import SubscriptionPlanViewSet

router = DefaultRouter()
router.register(r"plans", SubscriptionPlanViewSet, basename="subscription-plan")

urlpatterns = router.urls
