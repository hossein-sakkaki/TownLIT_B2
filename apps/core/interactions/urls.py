# apps/core/interactions/urls.py
from rest_framework.routers import DefaultRouter
from apps.core.interactions.views import InteractionReactionViewSet

router = DefaultRouter()

router.register(
    r"reactions",
    InteractionReactionViewSet,
    basename="interaction-reactions",
)

urlpatterns = router.urls
