from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    UserNotificationPreferenceViewSet,
    NotificationViewSet,
)

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'notification-preferences', UserNotificationPreferenceViewSet, basename='notification-preferences')

urlpatterns = router.urls
