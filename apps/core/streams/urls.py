# apps/core/streams/urls.py

from django.urls import path

from apps.core.streams.views import StreamViewSet


urlpatterns = [
    path("", StreamViewSet.as_view({"get": "list"}), name="stream-list"),
]