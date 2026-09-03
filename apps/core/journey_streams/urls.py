# apps/core/journey_streams/urls.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-03.
# Last Update by Hossein Sakkaki on 2026-09-03.

from django.urls import path

from apps.core.journey_streams.views import (
    JourneyStreamViewSet,
)


app_name = "journey_streams"


urlpatterns = [
    path(
        "rail/",
        JourneyStreamViewSet.as_view(
            {"get": "rail"}
        ),
        name="rail-list",
    ),
    path(
        "",
        JourneyStreamViewSet.as_view(
            {"get": "list"}
        ),
        name="active-list",
    ),
]