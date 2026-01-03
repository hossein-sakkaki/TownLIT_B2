# apps/posts/urls.py
from rest_framework.routers import DefaultRouter
from apps.posts.views.moments import MomentViewSet
from apps.posts.views.prayers import PrayViewSet
from apps.posts.views.announcements import AnnouncementViewSet
from apps.posts.views.witnesses import WitnessViewSet
from apps.posts.views.preaches import PreachViewSet
from apps.posts.views.lessons import LessonViewSet
from apps.posts.views.worships import WorshipViewSet
from apps.posts.views.media_contents import MediaContentViewSet
from apps.posts.views.libraries import LibraryViewSet
from apps.posts.views.missions import MissionViewSet
from apps.posts.views.service_events import ServiceEventViewSet
from apps.posts.views.conferences import ConferenceViewSet
from apps.posts.views.future_conferences import FutureConferenceViewSet

from apps.posts.views.testimonies import TestimonyViewSet
from apps.posts.views.reactions import ReactionViewSet
from apps.posts.views.comments import CommentViewSet

app_name = 'posts'
router = DefaultRouter()


# router.register(r'me/testimonies', MeTestimonyViewSet, basename='me-testimonies')
router.register(
    r'testimonies',
    TestimonyViewSet,
    basename='testimonies',
)

# centralized reactions
router.register(r'reactions', ReactionViewSet, basename='reaction')

# centralized comments 
router.register(r'comments', CommentViewSet, basename='comment')

router.register(r'moments', MomentViewSet, basename='moment')


# public/organizational resources
# router.register(r'testimonies', TestimonyViewSet, basename='testimony')
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
