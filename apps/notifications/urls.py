from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import UserNotificationPreferenceViewSet, NotificationViewSet

# ✅ Clean router without nested repetition
router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notifications')  # root-level endpoint
router.register(r'preferences', UserNotificationPreferenceViewSet, basename='notification-preferences')

urlpatterns = router.urls
