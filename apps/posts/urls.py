from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReactionViewSet, CommentViewSet, TestimonyViewSet, MomentViewSet, PrayViewSet, AnnouncementViewSet, 
    WitnessViewSet, LessonViewSet, PreachViewSet, WorshipViewSet, MediaContentViewSet, LibraryViewSet, 
    MissionViewSet, ConferenceViewSet, FutureConferenceViewSet
)

router = DefaultRouter()
router.register(r'reactions', ReactionViewSet, basename='reaction')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'testimonies', TestimonyViewSet, basename='testimony')
router.register(r'moments', MomentViewSet, basename='moments')
router.register(r'prays', PrayViewSet, basename='prays')
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'witnesses', WitnessViewSet, basename='witness')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'preaches', PreachViewSet, basename='preach')
router.register(r'worships', WorshipViewSet, basename='worship')
router.register(r'media-contents', MediaContentViewSet, basename='media_content')
router.register(r'libraries', LibraryViewSet, basename='library')
router.register(r'missions', MissionViewSet, basename='mission')
router.register(r'conferences', ConferenceViewSet, basename='conference')
router.register(r'future-conferences', FutureConferenceViewSet, basename='future_conference')

app_name = 'posts'

urlpatterns = [
    path('', include(router.urls)),
]