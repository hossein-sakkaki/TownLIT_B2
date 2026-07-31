# apps/core/journey_streams/urls.py

from django.urls import path

from apps.core.journey_streams.views import JourneyStreamViewSet


app_name = "journey_streams"


urlpatterns = [
    path("", JourneyStreamViewSet.as_view({"get": "list"}), name="active-list"),
]