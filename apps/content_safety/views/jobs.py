# apps/content_safety/views/jobs.py

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from rest_framework import mixins
from rest_framework.decorators import (
    action,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import (
    Response,
)
from rest_framework.viewsets import (
    GenericViewSet,
)

from apps.content_safety.models import (
    ContentSafetyJob,
)
from apps.content_safety.serializers.jobs import (
    ContentSafetyJobSerializer,
)
from apps.content_safety.services.media_jobs import (
    retry_content_safety_job,
)


class ContentSafetyJobViewSet(
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    Generic owner-facing Content Safety job API.

    No Testimony/Moment/Prayer-specific status or retry endpoints.
    """

    serializer_class = (
        ContentSafetyJobSerializer
    )

    permission_classes = [
        IsAuthenticated
    ]

    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        return (
            ContentSafetyJob.objects
            .filter(
                actor=self.request.user
            )
            .order_by(
                "-updated_at",
                "-id",
            )
        )

    @action(
        detail=True,
        methods=[
            "post"
        ],
        url_path="retry",
    )
    def retry(
        self,
        request,
        public_id=None,
    ):
        job = self.get_object()

        try:
            retried = (
                retry_content_safety_job(
                    job=job,
                    actor=request.user,
                )
            )

        except DjangoValidationError as exc:
            from rest_framework.exceptions import (
                ValidationError,
            )

            raise ValidationError(
                {
                    "detail": (
                        "; ".join(
                            exc.messages
                        )
                        if getattr(
                            exc,
                            "messages",
                            None,
                        )
                        else str(
                            exc
                        )
                    )
                }
            ) from exc

        return Response(
            self.get_serializer(
                retried
            ).data
        )