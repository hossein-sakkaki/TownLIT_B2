# apps/core/square/stream/urls.py

from django.urls import path
from .views import SquareStreamViewSet

urlpatterns = [
    path("stream/", SquareStreamViewSet.as_view({"get": "list"})),
]
