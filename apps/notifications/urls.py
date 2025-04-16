from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserNotificationPreferenceViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'notification-preferences', UserNotificationPreferenceViewSet, basename='notification-preferences')
router.register(r'notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('', include(router.urls)),
]
