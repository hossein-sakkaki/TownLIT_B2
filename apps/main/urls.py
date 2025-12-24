# apps/main/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from common.views.media_proxy import serve_s3_media_file
from .views import (
    TermsAndPolicyViewSet,
    UserAgreementViewSet,
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
    coming_soon_view,
    AvatarViewSet,
    GroupAvatarViewSet,
)

app_name = "main"  # For namespaced reversing; does not change URLs

router = DefaultRouter()
# Use unique basenames to avoid reverse name collisions across apps.
router.register(r'terms-and-policies', TermsAndPolicyViewSet, basename='main-terms-and-policies')
router.register(r"user-agreements", UserAgreementViewSet, basename="user-agreements")

router.register(r'faqs', FAQViewSet, basename='main-faqs')
router.register(r'site-announcements', SiteAnnouncementViewSet, basename='main-site-announcements')
router.register(r'user-feedbacks', UserFeedbackViewSet, basename='main-user-feedbacks')
router.register(r'user-action-logs', UserActionLogViewSet, basename='main-user-action-logs')
router.register(r'design-tokens', DesignTokensViewSet, basename='main-design-tokens')
router.register(r'icons', IconViewSet, basename='main-icons')
router.register(r'static-choice', StaticChoiceViewSet, basename='main-static-choice')
router.register(r'video-categories', VideoCategoryViewSet, basename='main-video-categories')
router.register(r'video-series', VideoSeriesViewSet, basename='main-video-series')
router.register(r'official-videos', OfficialVideoViewSet, basename='main-official-videos')
router.register(r'prayers', PrayerViewSet, basename='main-prayers')  # keep URL stable

router.register(r'media/avatar', AvatarViewSet, basename='main-avatar')
router.register(r"media/group-avatar", GroupAvatarViewSet, basename="main-group-avatar")

urlpatterns = router.urls + [
    # S3 media proxy endpoint (keep stable)
    path("media-proxy/", serve_s3_media_file, name="serve-s3-media"),
    
    # path('', coming_soon_view, name='coming-soon'),  # keep disabled if unused
]
