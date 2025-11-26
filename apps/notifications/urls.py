from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, UserNotificationPreferenceViewSet

router = DefaultRouter()

# Notifications list + actions
router.register(r'notifications', NotificationViewSet, basename='notifications')

# User preferences (CRUD)
router.register(r'notification-preferences', UserNotificationPreferenceViewSet,
                basename='notification-preferences')

urlpatterns = router.urls
