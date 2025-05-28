from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    TermsAndPolicyViewSet,
    FAQViewSet,
    SiteAnnouncementViewSet,
    UserFeedbackViewSet,
    UserActionLogViewSet,
    DesignTokensViewSet,
    IconViewSet,
    StaticChoiceViewSet,
    VideoCategoryViewSet,
    VideoSeriesViewSet,
    OfficialVideoViewSet,
    PrayerViewSet,
    coming_soon_view
)

router = DefaultRouter()
router.register(r'terms-and-policies', TermsAndPolicyViewSet, basename='terms-and-policies')
router.register(r'faqs', FAQViewSet, basename='faqs')
router.register(r'site-announcements', SiteAnnouncementViewSet, basename='site-announcements')
router.register(r'user-feedbacks', UserFeedbackViewSet, basename='user-feedback')
router.register(r'user-action-logs', UserActionLogViewSet, basename='user-action-logs')
router.register(r'design-tokens', DesignTokensViewSet, basename='design-tokens')
router.register(r'icons', IconViewSet, basename='icons')
router.register(r'static-choice', StaticChoiceViewSet, basename='static-choice')
router.register(r'video-categories', VideoCategoryViewSet, basename='video-categories')
router.register(r'video-series', VideoSeriesViewSet, basename='video-series')
router.register(r'official-videos', OfficialVideoViewSet, basename='official-videos')
router.register(r'prayers', PrayerViewSet, basename='prayers')

urlpatterns = [
    path('', coming_soon_view, name='coming-soon'),
]

urlpatterns += router.urls