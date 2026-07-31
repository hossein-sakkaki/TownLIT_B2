# apps/creative_editor/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.creative_editor.views import (
    CreativeCompositionViewSet,
    CreativeRenderJobViewSet,
)


router = DefaultRouter()

router.register(
    "compositions",
    CreativeCompositionViewSet,
    basename="creative-composition",
)

router.register(
    "render-jobs",
    CreativeRenderJobViewSet,
    basename="creative-render-job",
)


urlpatterns = [
    path("", include(router.urls)),
]