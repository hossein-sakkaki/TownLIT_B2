from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import AuthViewSet, SocialLinksViewSet, IdentityViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'social-links', SocialLinksViewSet, basename='social-links')
router.register(r'identity', IdentityViewSet, basename='identity')

urlpatterns = router.urls
