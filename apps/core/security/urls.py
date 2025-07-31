# apps/core/security/urls.py
from rest_framework.routers import DefaultRouter
from .views import LITShieldAccessViewSet

router = DefaultRouter()
router.register(r"", LITShieldAccessViewSet, basename="litshield")

urlpatterns = router.urls
