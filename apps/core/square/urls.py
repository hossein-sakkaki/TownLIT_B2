# apps/core/square/urls.py

from django.urls import include, path
from apps.core.square.views import SquareViewSet

urlpatterns = [
    # Main square feed
    path("", SquareViewSet.as_view({"get": "list"}), name="square-feed"),

    # Stream (open / scroll from seed)
    path("", include("apps.core.square.stream.urls")),
]
