# apps/posts/urls.py
from rest_framework.routers import DefaultRouter
from apps.posts.views.moments import MomentViewSet
from apps.posts.views.prayers import PrayViewSet
from apps.posts.views.testimonies import TestimonyViewSet
from apps.posts.views.journeys import (
    JourneyEntryViewSet,
    JourneyViewSet,
)

from apps.posts.views.reactions import ReactionViewSet
from apps.posts.views.comments import CommentViewSet

from apps.posts.views.witnesses import WitnessViewSet


app_name = 'posts'
router = DefaultRouter()


router.register(r'testimonies', TestimonyViewSet, basename='testimonies')
router.register(r'moments', MomentViewSet, basename='moment')
router.register(r'prayers', PrayViewSet, basename='prayer')
router.register(r"journeys", JourneyViewSet, basename="journey")
router.register(r"journey-entries", JourneyEntryViewSet, basename="journey-entry")

# centralized reactions
router.register(r'reactions', ReactionViewSet, basename='reaction')

# centralized comments 
router.register(r'comments', CommentViewSet, basename='comment')

# public/organizational resources
router.register(r'witnesses', WitnessViewSet, basename='witness')

urlpatterns = router.urls
