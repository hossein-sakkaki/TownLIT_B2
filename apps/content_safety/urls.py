# apps/content_safety/urls.py

from django.urls import (
    include,
    path,
)

from rest_framework.routers import (
    SimpleRouter,
)

from apps.content_safety.views.jobs import (
    ContentSafetyJobViewSet,
)


router = SimpleRouter()

router.register(
    "media-jobs",
    ContentSafetyJobViewSet,
    basename="content-safety-media-job",
)


urlpatterns = [
    path(
        "",
        include(
            router.urls
        ),
    ),
]