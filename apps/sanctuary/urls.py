# apps/sanctuary/urls.py

from rest_framework.routers import DefaultRouter

from apps.sanctuary.views import (
    SanctuaryRequestViewSet,
    SanctuaryReviewViewSet,          # ✅ council voting
    SanctuaryOutcomeViewSet,
    SanctuaryHistoryViewSet,
    SanctuaryParticipationViewSet,
)

router = DefaultRouter()

# Core workflow
router.register(r"sanctuary-requests", SanctuaryRequestViewSet, basename="sanctuary-requests")

# ✅ rename: council votes endpoint
router.register(r"council-reviews", SanctuaryReviewViewSet, basename="council-reviews")

router.register(r"sanctuary-outcomes", SanctuaryOutcomeViewSet, basename="sanctuary-outcomes")

# Read-only history endpoints
router.register(r"sanctuary-history", SanctuaryHistoryViewSet, basename="sanctuary-history")

# Settings panel (opt-in / opt-out / status)
router.register(r"sanctuary-participation", SanctuaryParticipationViewSet, basename="sanctuary-participation")

urlpatterns = router.urls
