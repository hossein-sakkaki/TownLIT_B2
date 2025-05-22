# moderation/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollaborationRequestViewSet, JobApplicationViewSet, AccessRequestViewSet

router = DefaultRouter()
router.register(r'collaborations', CollaborationRequestViewSet, basename='collaborations')
router.register(r'job-applications', JobApplicationViewSet, basename='job-applications')
router.register(r'access-requests', AccessRequestViewSet, basename='access-requests')


urlpatterns = [
    path('', include(router.urls)),
]
