# apps/content_safety/view_mixins.py

from __future__ import annotations

from collections.abc import Mapping

from rest_framework import status

from apps.content_safety.models import (
    ContentSafetyJob,
)
from apps.content_safety.serializers.jobs import (
    ContentSafetyJobSerializer,
)
from apps.content_safety.services.media_jobs import (
    schedule_configured_content_safety_jobs,
)


class ContentSafetyJobResponseMixin:
    """
    Reusable DRF mixin for models using ContentSafetyMediaTargetMixin.

    Domain perform_create/perform_update only needs to call
    schedule_content_safety_jobs().
    """

    _response_content_safety_job_ids: list[int]

    def reset_content_safety_response_jobs(
        self,
    ) -> None:
        self._response_content_safety_job_ids = []


    def register_content_safety_jobs(
        self,
        jobs,
    ) -> None:
        if not hasattr(
            self,
            "_response_content_safety_job_ids",
        ):
            self.reset_content_safety_response_jobs()

        known = set(
            self._response_content_safety_job_ids
        )

        for job in jobs:
            job_id = getattr(
                job,
                "pk",
                None,
            )

            if (
                job_id
                and job_id not in known
            ):
                self._response_content_safety_job_ids.append(
                    job_id
                )

                known.add(
                    job_id
                )


    def schedule_content_safety_jobs(
        self,
        *,
        instance,
        submitted_data,
    ):
        jobs = (
            schedule_configured_content_safety_jobs(
                instance=instance,
                actor=self.request.user,
                submitted_data=submitted_data,
            )
        )

        self.register_content_safety_jobs(
            jobs
        )

        return jobs


    def finalize_content_safety_response(
        self,
        response,
    ):
        job_ids = getattr(
            self,
            "_response_content_safety_job_ids",
            [],
        )

        if not job_ids:
            return response

        fresh_by_id = {
            job.pk: job
            for job in (
                ContentSafetyJob.objects
                .filter(
                    pk__in=job_ids
                )
            )
        }

        jobs = [
            fresh_by_id[job_id]
            for job_id in job_ids
            if job_id in fresh_by_id
        ]

        if not jobs:
            return response

        if isinstance(
            response.data,
            Mapping,
        ):
            payload = dict(
                response.data
            )

            payload[
                "content_safety_jobs"
            ] = (
                ContentSafetyJobSerializer(
                    jobs,
                    many=True,
                ).data
            )

            response.data = payload

        response.status_code = (
            status.HTTP_202_ACCEPTED
        )

        return response


    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        self.reset_content_safety_response_jobs()

        response = super().create(
            request,
            *args,
            **kwargs,
        )

        return self.finalize_content_safety_response(
            response
        )


    def update(
        self,
        request,
        *args,
        **kwargs,
    ):
        self.reset_content_safety_response_jobs()

        response = super().update(
            request,
            *args,
            **kwargs,
        )

        return self.finalize_content_safety_response(
            response
        )