#
# apps/media_conversion/services/availability.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-25.
# Last Update by Hossein Sakkaki on 2026-08-25.
#

from __future__ import annotations

import logging

from django.db import transaction

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
)


logger = logging.getLogger(__name__)


def maybe_mark_media_target_available_by_id(
    job_id: int,
) -> bool:
    """
    Reload one MediaConversionJob and attempt target finalization.

    Returns True only when this call transitioned the target from
    not-converted to converted.
    """

    job = (
        MediaConversionJob.objects
        .select_related("content_type")
        .filter(pk=job_id)
        .first()
    )

    if job is None:
        return False

    return maybe_mark_media_target_available(
        job
    )


def maybe_mark_media_target_available(
    job: MediaConversionJob,
) -> bool:
    """
    Mark a media target converted only when its current required media
    generations are ready.

    Important:
    - Historical FAILED/CANCELED jobs do not automatically poison readiness.
    - A Safety-gated video that has not entered Media Conversion yet keeps
      the target unavailable because its current source has no DONE job.
    - Optional/secondary media can be excluded from target availability
      through the model's media_conversion_config.
    - The is_converted transition is atomic, preventing duplicate
      on_available() execution from parallel completed jobs.
    """

    if not job or not getattr(
        job,
        "pk",
        None,
    ):
        return False

    try:
        authoritative_job = (
            MediaConversionJob.objects
            .select_related("content_type")
            .filter(pk=job.pk)
            .first()
        )

        if authoritative_job is None:
            return False

        if (
            authoritative_job.status
            != MediaJobStatus.DONE
        ):
            return False

        content_type = (
            authoritative_job.content_type
        )

        model_class = (
            content_type.model_class()
            if content_type
            else None
        )

        if model_class is None:
            return False

        transitioned = False
        target = None

        with transaction.atomic():
            target = (
                model_class._base_manager
                .select_for_update()
                .filter(
                    pk=authoritative_job.object_id
                )
                .first()
            )

            if target is None:
                return False

            readiness_hook = getattr(
                target,
                "media_conversion_target_ready_for_availability",
                None,
            )

            if callable(
                readiness_hook
            ):
                if not readiness_hook():
                    return False

            else:
                # Backward-compatible fallback for legacy targets that do not
                # expose field-aware MediaConversionMixin readiness.
                jobs = (
                    MediaConversionJob.objects
                    .filter(
                        content_type=content_type,
                        object_id=authoritative_job.object_id,
                    )
                )

                if not jobs.exists():
                    return False

                if jobs.exclude(
                    status=MediaJobStatus.DONE
                ).exists():
                    return False

            if not hasattr(
                target,
                "is_converted",
            ):
                return False

            if bool(
                target.is_converted
            ):
                return False

            updated = (
                model_class._base_manager
                .filter(
                    pk=target.pk,
                    is_converted=False,
                )
                .update(
                    is_converted=True
                )
            )

            if updated != 1:
                return False

            target.is_converted = True
            transitioned = True

        if not transitioned:
            return False

        is_available = getattr(
            target,
            "is_available",
            None,
        )

        on_available = getattr(
            target,
            "on_available",
            None,
        )

        if (
            callable(
                is_available
            )
            and callable(
                on_available
            )
        ):
            try:
                if is_available():
                    on_available()

            except Exception:
                logger.exception(
                    (
                        "Media target on_available failed: "
                        "%s[%s]"
                    ),
                    model_class.__name__,
                    getattr(
                        target,
                        "pk",
                        None,
                    ),
                )

        logger.info(
            (
                "✅ Media target became available: "
                "%s[%s] completed_job=%s"
            ),
            model_class.__name__,
            getattr(
                target,
                "pk",
                None,
            ),
            authoritative_job.pk,
        )

        return True

    except Exception:
        logger.exception(
            (
                "Failed to evaluate media target availability "
                "for MediaConversionJob id=%s"
            ),
            getattr(
                job,
                "pk",
                None,
            ),
        )

        return False