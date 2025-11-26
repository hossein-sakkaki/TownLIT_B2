from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import AuthViewSet, SocialLinksViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'social-links', SocialLinksViewSet, basename='social-links')

urlpatterns = router.urls
