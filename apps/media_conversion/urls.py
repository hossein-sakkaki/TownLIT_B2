# apps/media_conversion/urls.py
from rest_framework.routers import DefaultRouter
from apps.media_conversion.views import MediaConversionJobViewSet

router = DefaultRouter()
router.register(r"media-jobs", MediaConversionJobViewSet, basename="media-jobs")

urlpatterns = router.urls
