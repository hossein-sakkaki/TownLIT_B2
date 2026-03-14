# apps/accounts/urls.py

from rest_framework.routers import DefaultRouter

from apps.accounts.views.auth_views import AuthViewSet
from apps.accounts.views.social_views import SocialLinksViewSet
from apps.accounts.views.identity_views import IdentityViewSet
from apps.accounts.views.townlit_verification_views import TownlitVerificationViewSet


router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'social-links', SocialLinksViewSet, basename='social-links')
router.register(r'identity', IdentityViewSet, basename='identity')
router.register(r'townlit-verification', TownlitVerificationViewSet, basename='townlit-verification')

urlpatterns = router.urls