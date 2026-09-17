# apps/posts/urls.py

from django.urls import path

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
from apps.posts.views.share_preview import (
    PostSharePreviewImageView,
    PostSharePreviewView,
)

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

urlpatterns = [
    path(
        "share-preview/<str:kind>/<str:slug>/",
        PostSharePreviewView.as_view(),
        name="share-preview",
    ),
    path(
        "share-preview/<str:kind>/<str:slug>/image/",
        PostSharePreviewImageView.as_view(),
        name="share-preview-image",
    ),
    *router.urls,
]
