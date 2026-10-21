# apps/content_safety/views/jobs.py
# TownLIT
#
# Created by Hossein Sakkaki (original creation date not recorded).
# Last Update by Hossein Sakkaki on 2026-10-19.


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

    def get_object(self):
        from django.shortcuts import get_object_or_404
        from rest_framework.exceptions import NotFound
        job = get_object_or_404(
            ContentSafetyJob.objects.select_related("content_type"),
            public_id=self.kwargs[self.lookup_url_kwarg],
        )
        target = job.content_object
        hook = getattr(target, "can_manage_content_safety", None)
        permitted = bool(hook(actor=self.request.user)) if callable(hook) else job.actor_id == self.request.user.pk
        if not permitted:
            raise NotFound()
        self.check_object_permissions(self.request, job)
        return job

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
