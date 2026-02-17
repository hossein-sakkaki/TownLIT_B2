# apps/asset_delivery/urls.py

from rest_framework.routers import DefaultRouter
from apps.asset_delivery.views import AssetPlaybackViewSet

router = DefaultRouter()
router.register(r"playback", AssetPlaybackViewSet, basename="asset-playback")

urlpatterns = router.urls
