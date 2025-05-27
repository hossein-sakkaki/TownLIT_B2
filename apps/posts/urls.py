from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ReactionViewSet, CommentViewSet,
    MomentViewSet, TestimonyViewSet, PrayViewSet, AnnouncementViewSet,
    WitnessViewSet, PreachViewSet, LessonViewSet, WorshipViewSet,
    MediaContentViewSet, MissionViewSet, LibraryViewSet, ServiceEventViewSet,
    ConferenceViewSet, FutureConferenceViewSet
)

router = DefaultRouter()
router.register(r'reactions', ReactionViewSet, basename='reaction')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'moments', MomentViewSet, basename='moment')
router.register(r'testimonies', TestimonyViewSet, basename='testimony')
router.register(r'prayers', PrayViewSet, basename='prayer')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'witnesses', WitnessViewSet, basename='witness')
router.register(r'preaches', PreachViewSet, basename='preach')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'worships', WorshipViewSet, basename='worship')
router.register(r'media-contents', MediaContentViewSet, basename='media-content')
router.register(r'libraries', LibraryViewSet, basename='library')
router.register(r'missions', MissionViewSet, basename='mission')
router.register(r'service-events', ServiceEventViewSet, basename='service-event')
router.register(r'conferences', ConferenceViewSet, basename='conference')
router.register(r'future-conferences', FutureConferenceViewSet, basename='future-conference')

urlpatterns = router.urls
