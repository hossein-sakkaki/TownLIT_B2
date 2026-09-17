# apps/core/square/urls.py

from django.urls import include, path
from apps.core.square.views import SquareViewSet
from apps.core.square.search_views import (
    SquareContentSearchView,
)

urlpatterns = [
    # Main square feed
    path(
        "", 
        SquareViewSet.as_view({"get": "list"}), 
        name="square-feed"),
    
    path(
        "search/",
        SquareContentSearchView.as_view(),
        name="square-content-search",
    ),
]
