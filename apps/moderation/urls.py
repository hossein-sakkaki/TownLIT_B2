# moderation/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollaborationRequestViewSet, JobApplicationViewSet

router = DefaultRouter()
router.register(r'collaborations', CollaborationRequestViewSet, basename='collaborations')
router.register(r'job-applications', JobApplicationViewSet, basename='job-applications')

urlpatterns = [
    path('', include(router.urls)),
]
