# apps/content_safety/tasks.py

from __future__ import annotations

import logging
import mimetypes

from celery import shared_task

from django.core.files.storage import (
    default_storage,
)
from django.db import close_old_connections
from django.utils import timezone

from apps.content_safety.enums import (
    ContentSafetyJobStage,
    ContentSafetyJobStatus,
    SafetyDecision,
    SafetyInputType,
)
from apps.content_safety.exceptions import (
    ContentSafetyUnavailableError,
)
from apps.content_safety.models import (
    ContentSafetyJob,
)
from apps.content_safety.services.media_jobs import (
    content_safety_requires_conversion_handoff,
    try_handoff_approved_media_to_conversion,
)
from apps.content_safety.services.video import (
    check_video_file_safety,
)


logger = logging.getLogger(
    __name__
)


def _clean_key(
    value,
) -> str:
    return str(
        value
        or ""
    ).strip().lstrip(
        "/"
    )


def _load_current_job(
    *,
    job_id: int,
    task_id: str,
) -> ContentSafetyJob | None:
    return (
        ContentSafetyJob.objects
        .select_related(
            "content_type",
            "actor",
        )
        .filter(
            pk=job_id,
            task_id=task_id,
        )
        .first()
    )


def _update_current_job(
    *,
    job_id: int,
    task_id: str,
    **updates,
) -> bool:
    updates[
        "heartbeat_at"
    ] = timezone.now()

    updated = (
        ContentSafetyJob.objects
        .filter(
            pk=job_id,
            task_id=task_id,
        )
        .update(
            **updates
        )
    )

    return updated == 1


def _source_is_current(
    *,
    job: ContentSafetyJob,
    target,
) -> bool:
    value = getattr(
        target,
        job.field_name,
        None,
    )

    current_source = _clean_key(
        getattr(
            value,
            "name",
            None,
        )
    )

    return (
        current_source
        == _clean_key(
            job.source_path
        )
    )


def _mark_canceled(
    *,
    job_id: int,
    task_id: str,
    message: str,
) -> None:
    _update_current_job(
        job_id=job_id,
        task_id=task_id,
        status=(
            ContentSafetyJobStatus.CANCELED
        ),
        stage=(
            ContentSafetyJobStage.CANCELED
        ),
        retryable=False,
        progress=100,
        message=message,
        error="",
        finished_at=timezone.now(),
    )


def _mark_failed(
    *,
    job_id: int,
    task_id: str,
    message: str,
    error: str = "",
    retryable: bool,
    reason_code: str = "",
    preserve_allow: bool = False,
    stage: str = ContentSafetyJobStage.FAILED,
) -> None:
    updates = {
        "status": (
            ContentSafetyJobStatus.FAILED
        ),
        "stage": stage,
        "retryable": retryable,
        "progress": 100,
        "message": message,
        "error": error,
        "finished_at": timezone.now(),
    }

    if reason_code:
        updates[
            "reason_code"
        ] = reason_code

    if not preserve_allow:
        updates[
            "decision"
        ] = ""

    _update_current_job(
        job_id=job_id,
        task_id=task_id,
        **updates,
    )


def _finalize_safety_only_target(
    *,
    job: ContentSafetyJob,
    target,
) -> None:
    """
    Allow a safety-only domain target to complete its own readiness state.

    Conversion-backed post models never enter this hook.
    """

    hook = getattr(
        target,
        "on_content_safety_media_approved",
        None,
    )

    if not callable(
        hook
    ):
        return

    hook(
        field_name=job.field_name,
        source_path=_clean_key(
            job.source_path
        ),
    )


@shared_task(
    bind=True,
)
def process_content_safety_media_job(
    self,
    *,
    job_id: int,
):
    """
    Generic asynchronous media safety task.

    v1 processes VIDEO.

    Two supported completion modes:

    1. Conversion-backed target:
       Safety ALLOW -> Media Conversion handoff.

    2. Safety-only target:
       Safety ALLOW -> optional domain finalization -> DONE.

    Existing post-like targets preserve conversion handoff by default.
    """

    close_old_connections()

    task_id = str(
        getattr(
            self.request,
            "id",
            "",
        )
        or ""
    )

    try:
        job = _load_current_job(
            job_id=job_id,
            task_id=task_id,
        )

        if job is None:
            return

        if (
            job.status
            != ContentSafetyJobStatus.QUEUED
        ):
            return

        # -------------------------------------------------
        # Start processing
        # -------------------------------------------------
        if not _update_current_job(
            job_id=job_id,
            task_id=task_id,
            status=(
                ContentSafetyJobStatus.PROCESSING
            ),
            stage=(
                ContentSafetyJobStage.CHECKING
            ),
            progress=10,
            message=(
                "Checking media for community safety"
            ),
            error="",
            started_at=(
                job.started_at
                or timezone.now()
            ),
        ):
            return

        job = _load_current_job(
            job_id=job_id,
            task_id=task_id,
        )

        if job is None:
            return

        target = job.content_object

        if target is None:
            _mark_canceled(
                job_id=job_id,
                task_id=task_id,
                message=(
                    "Safety check canceled because the content "
                    "no longer exists."
                ),
            )
            return

        if not _source_is_current(
            job=job,
            target=target,
        ):
            _mark_canceled(
                job_id=job_id,
                task_id=task_id,
                message=(
                    "Safety check canceled because the media changed."
                ),
            )
            return

        try:
            handoff_to_conversion = (
                content_safety_requires_conversion_handoff(
                    instance=target,
                    field_name=job.field_name,
                )
            )

        except Exception as exc:
            logger.exception(
                (
                    "Invalid Content Safety target configuration "
                    "job=%s"
                ),
                job_id,
            )

            _mark_failed(
                job_id=job_id,
                task_id=task_id,
                message=(
                    "This media safety configuration is invalid."
                ),
                error=str(
                    exc
                ),
                retryable=False,
            )
            return

        source_path = _clean_key(
            job.source_path
        )

        # -------------------------------------------------
        # Safety provider work
        # -------------------------------------------------
        #
        # An ALLOW decision may already exist when retrying:
        #
        # - Media Conversion handoff for post-like targets
        # - domain finalization for safety-only targets
        #
        # In both cases provider work must not be repeated.
        # -------------------------------------------------
        if (
            job.decision
            != SafetyDecision.ALLOW
        ):
            if (
                job.input_type
                != SafetyInputType.VIDEO
            ):
                _mark_failed(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "This media type is not supported by "
                        "asynchronous safety."
                    ),
                    retryable=False,
                )
                return

            if (
                not source_path
                or not default_storage.exists(
                    source_path
                )
            ):
                _mark_failed(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "The source media is no longer available."
                    ),
                    retryable=False,
                )
                return

            mime_type = str(
                job.mime_type
                or mimetypes.guess_type(
                    source_path
                )[0]
                or ""
            ).strip().lower()

            try:
                with default_storage.open(
                    source_path,
                    "rb",
                ) as file_obj:
                    result = check_video_file_safety(
                        file_obj=file_obj,
                        context=job.context,
                        actor=job.actor,
                        field_name=job.field_name,
                        mime_type=(
                            mime_type
                            or None
                        ),
                    )

            except ContentSafetyUnavailableError as exc:
                logger.warning(
                    (
                        "Content Safety temporarily unavailable "
                        "job=%s"
                    ),
                    job_id,
                    exc_info=True,
                )

                _mark_failed(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "Could not verify this media right now."
                    ),
                    error=str(
                        exc
                    ),
                    reason_code=(
                        "provider_unavailable"
                    ),
                    retryable=True,
                )
                return

            except (
                TypeError,
                ValueError,
            ) as exc:
                logger.warning(
                    (
                        "Invalid media during Content Safety "
                        "job=%s: %s"
                    ),
                    job_id,
                    exc,
                )

                _mark_failed(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "This media could not be inspected."
                    ),
                    error=str(
                        exc
                    ),
                    retryable=False,
                )
                return

            except Exception as exc:
                logger.exception(
                    (
                        "Unexpected Content Safety failure "
                        "job=%s"
                    ),
                    job_id,
                )

                _mark_failed(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "Could not complete the safety check."
                    ),
                    error=str(
                        exc
                    ),
                    retryable=True,
                )
                return

            # -------------------------------------------------
            # Re-check generation after expensive provider work
            # -------------------------------------------------
            job = _load_current_job(
                job_id=job_id,
                task_id=task_id,
            )

            if job is None:
                return

            target = job.content_object

            if target is None:
                _mark_canceled(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "Safety check canceled because the content "
                        "no longer exists."
                    ),
                )
                return

            if not _source_is_current(
                job=job,
                target=target,
            ):
                _mark_canceled(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "Safety check canceled because the media changed."
                    ),
                )
                return

            # -------------------------------------------------
            # BLOCK / REVIEW
            # -------------------------------------------------
            if (
                result.decision
                != SafetyDecision.ALLOW
            ):
                message = (
                    "This media cannot be posted."
                    if (
                        result.decision
                        == SafetyDecision.BLOCK
                    )
                    else (
                        "This media needs changes before posting."
                    )
                )

                _update_current_job(
                    job_id=job_id,
                    task_id=task_id,
                    status=(
                        ContentSafetyJobStatus.DONE
                    ),
                    stage=(
                        ContentSafetyJobStage.FINISHED
                    ),
                    decision=str(
                        result.decision
                    ),
                    risk_level=str(
                        result.risk_level
                        or ""
                    ),
                    reason_code=str(
                        result.reason_code
                        or ""
                    ),
                    input_hash=str(
                        result.input_hash
                        or ""
                    ),
                    retryable=False,
                    progress=100,
                    message=message,
                    error="",
                    conversion_job_id=None,
                    finished_at=timezone.now(),
                )

                return

            # -------------------------------------------------
            # ALLOW
            # -------------------------------------------------
            #
            # Persist ALLOW before downstream work so a retry never
            # repeats provider inspection.
            # -------------------------------------------------
            if handoff_to_conversion:
                if not _update_current_job(
                    job_id=job_id,
                    task_id=task_id,
                    decision=(
                        SafetyDecision.ALLOW
                    ),
                    risk_level=str(
                        result.risk_level
                        or ""
                    ),
                    reason_code=str(
                        result.reason_code
                        or "safe"
                    ),
                    input_hash=str(
                        result.input_hash
                        or ""
                    ),
                    retryable=False,
                    progress=90,
                    stage=(
                        ContentSafetyJobStage.HANDOFF
                    ),
                    message=(
                        "Safety check passed. Preparing media processing."
                    ),
                ):
                    return

            else:
                if not _update_current_job(
                    job_id=job_id,
                    task_id=task_id,
                    decision=(
                        SafetyDecision.ALLOW
                    ),
                    risk_level=str(
                        result.risk_level
                        or ""
                    ),
                    reason_code=str(
                        result.reason_code
                        or "safe"
                    ),
                    input_hash=str(
                        result.input_hash
                        or ""
                    ),
                    retryable=False,
                    progress=95,
                    stage=(
                        ContentSafetyJobStage.CHECKING
                    ),
                    message=(
                        "Safety check passed. Finalizing."
                    ),
                ):
                    return

        else:
            # -------------------------------------------------
            # Downstream-only retry after authoritative ALLOW
            # -------------------------------------------------
            if handoff_to_conversion:
                if not _update_current_job(
                    job_id=job_id,
                    task_id=task_id,
                    progress=90,
                    stage=(
                        ContentSafetyJobStage.HANDOFF
                    ),
                    message=(
                        "Preparing media processing"
                    ),
                ):
                    return

            else:
                if not _update_current_job(
                    job_id=job_id,
                    task_id=task_id,
                    progress=95,
                    stage=(
                        ContentSafetyJobStage.CHECKING
                    ),
                    message=(
                        "Finalizing safety approval"
                    ),
                ):
                    return

        # -------------------------------------------------
        # Re-read before downstream completion
        # -------------------------------------------------
        job = _load_current_job(
            job_id=job_id,
            task_id=task_id,
        )

        if job is None:
            return

        target = job.content_object

        if target is None:
            _mark_canceled(
                job_id=job_id,
                task_id=task_id,
                message=(
                    "Safety check canceled because the content "
                    "no longer exists."
                ),
            )
            return

        if not _source_is_current(
            job=job,
            target=target,
        ):
            _mark_canceled(
                job_id=job_id,
                task_id=task_id,
                message=(
                    "Safety check canceled because the media changed."
                ),
            )
            return

        # -------------------------------------------------
        # Safety-only completion
        # -------------------------------------------------
        if not handoff_to_conversion:
            try:
                refreshed_job = _load_current_job(
                    job_id=job_id,
                    task_id=task_id,
                )

                if refreshed_job is None:
                    return

                _finalize_safety_only_target(
                    job=refreshed_job,
                    target=target,
                )

            except Exception as exc:
                logger.exception(
                    (
                        "Content Safety domain finalization failed "
                        "job=%s"
                    ),
                    job_id,
                )

                _mark_failed(
                    job_id=job_id,
                    task_id=task_id,
                    message=(
                        "Safety passed, but the content could not be finalized."
                    ),
                    error=str(
                        exc
                    ),
                    retryable=True,
                    preserve_allow=True,
                    stage=(
                        ContentSafetyJobStage.FAILED
                    ),
                )
                return

            if not _update_current_job(
                job_id=job_id,
                task_id=task_id,
                status=(
                    ContentSafetyJobStatus.DONE
                ),
                stage=(
                    ContentSafetyJobStage.FINISHED
                ),
                decision=(
                    SafetyDecision.ALLOW
                ),
                retryable=False,
                progress=100,
                message=(
                    "Safety check passed."
                ),
                error="",
                conversion_job_id=None,
                finished_at=timezone.now(),
            ):
                return

            logger.info(
                (
                    "✅ Content Safety completed without "
                    "Media Conversion job=%s"
                ),
                job_id,
            )

            return

        # -------------------------------------------------
        # Safety -> Media Conversion handoff
        # -------------------------------------------------
        try:
            refreshed_job = _load_current_job(
                job_id=job_id,
                task_id=task_id,
            )

            if refreshed_job is None:
                return

            conversion_job = (
                try_handoff_approved_media_to_conversion(
                    job=refreshed_job
                )
            )

        except Exception as exc:
            logger.exception(
                (
                    "Content Safety -> Media Conversion "
                    "handoff failed job=%s"
                ),
                job_id,
            )

            _mark_failed(
                job_id=job_id,
                task_id=task_id,
                message=(
                    "Safety passed, but media processing could not start."
                ),
                error=str(
                    exc
                ),
                retryable=True,
                preserve_allow=True,
                stage=(
                    ContentSafetyJobStage.HANDOFF_FAILED
                ),
            )
            return

        # -------------------------------------------------
        # Conversion handoff complete
        # -------------------------------------------------
        if not _update_current_job(
            job_id=job_id,
            task_id=task_id,
            status=(
                ContentSafetyJobStatus.DONE
            ),
            stage=(
                ContentSafetyJobStage.HANDED_OFF
            ),
            decision=(
                SafetyDecision.ALLOW
            ),
            retryable=False,
            progress=100,
            message=(
                "Safety check passed. Media processing has started."
            ),
            error="",
            conversion_job_id=(
                conversion_job.pk
            ),
            finished_at=timezone.now(),
        ):
            return

        logger.info(
            (
                "✅ Content Safety handed off "
                "job=%s conversion_job=%s"
            ),
            job_id,
            conversion_job.pk,
        )

    finally:
        close_old_connections()