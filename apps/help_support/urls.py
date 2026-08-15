# apps/help_support/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.help_support.views import (
    SupportBootstrapViewSet,
    SupportTicketViewSet,
)


router = DefaultRouter()
router.register(
    "tickets",
    SupportTicketViewSet,
    basename="support-ticket",
)


urlpatterns = [
    path(
        "bootstrap/",
        SupportBootstrapViewSet.as_view(
            {
                "get": "list",
            }
        ),
        name="support-bootstrap",
    ),
]

urlpatterns += router.urls