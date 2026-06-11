# apps/core/boundaries/urls.py

from rest_framework.routers import DefaultRouter

from apps.core.boundaries.views import UserBoundaryViewSet

router = DefaultRouter()
router.register(r"boundaries", UserBoundaryViewSet, basename="user-boundaries")

urlpatterns = router.urls