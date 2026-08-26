# apps/content_safety/services/media_jobs.py

from __future__ import annotations

import logging
import mimetypes
import uuid

from dataclasses import dataclass
from typing import Mapping

from django.conf import settings
from django.contrib.contenttypes.models import (
    ContentType,
)
from django.core.exceptions import (
    ValidationError,
)
from django.core.files.storage import (
    default_storage,
)
from django.db import transaction
from django.utils import timezone

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
)
from apps.content_safety.enums import (
    ContentSafetyJobStage,
    ContentSafetyJobStatus,
    SafetyDecision,
    SafetyInputType,
)
from apps.content_safety.models import (
    ContentSafetyJob,
)

logger = logging.getLogger(
    __name__
)


@dataclass(
    frozen=True
)
class ConfiguredMediaSafetyField:
    field_name: str
    input_type: str
    context: str
    conversion_kind: str

    # Existing post-like targets default to the current behavior:
    # Content Safety ALLOW -> Media Conversion handoff.
    #
    # Safety-only targets such as Group Messenger video
    # explicitly set this to False.
    handoff_to_conversion: bool = True


def _enum_value(
    value,
) -> str:
    return str(
        getattr(
            value,
            "value",
            value,
        )
        or ""
    ).strip()


def _clean_storage_key(
    value,
) -> str:
    return str(
        value
        or ""
    ).strip().lstrip(
        "/"
    )


def _target_content_type(
    instance,
):
    return (
        ContentType.objects
        .get_for_model(
            instance,
            for_concrete_model=False,
        )
    )


def _current_source_path(
    instance,
    field_name: str,
) -> str:
    value = getattr(
        instance,
        field_name,
        None,
    )

    return _clean_storage_key(
        getattr(
            value,
            "name",
            None,
        )
    )


def _is_final_media_source(
    *,
    instance,
    conversion_kind: str,
    source_path: str,
) -> bool:
    if not source_path:
        return False

    checker = getattr(
        instance,
        "_is_final_name",
        None,
    )

    if callable(
        checker
    ):
        try:
            return bool(
                checker(
                    conversion_kind,
                    source_path,
                )
            )
        except Exception:
            pass

    if conversion_kind == "video":
        return source_path.lower().endswith(
            ".m3u8"
        )

    if conversion_kind == "audio":
        return source_path.lower().endswith(
            ".mp3"
        )

    return False


def configured_media_safety_fields(
    instance,
) -> list[ConfiguredMediaSafetyField]:
    getter = getattr(
        instance,
        "get_content_safety_media_config",
        None,
    )

    if callable(
        getter
    ):
        config = getter()

    else:
        config = getattr(
            instance,
            "content_safety_media_config",
            {},
        )

    if not isinstance(
        config,
        dict,
    ):
        raise ValidationError(
            "Invalid Content Safety media configuration."
        )

    fields: list[
        ConfiguredMediaSafetyField
    ] = []

    for raw_field_name, metadata in config.items():
        field_name = str(
            raw_field_name
            or ""
        ).strip()

        if not field_name:
            raise ValidationError(
                "Content Safety media field name is missing."
            )

        if not isinstance(
            metadata,
            dict,
        ):
            raise ValidationError(
                (
                    "Content Safety media configuration "
                    f"for '{field_name}' is invalid."
                )
            )

        input_type = _enum_value(
            metadata.get(
                "input_type"
            )
        )

        context = _enum_value(
            metadata.get(
                "context"
            )
        )

        conversion_kind = _enum_value(
            metadata.get(
                "conversion_kind"
            )
        )

        raw_handoff_to_conversion = (
            metadata.get(
                "handoff_to_conversion",
                True,
            )
        )

        if not input_type:
            raise ValidationError(
                (
                    "Content Safety input type is missing "
                    f"for '{field_name}'."
                )
            )

        if not context:
            raise ValidationError(
                (
                    "Content Safety context is missing "
                    f"for '{field_name}'."
                )
            )

        if not conversion_kind:
            raise ValidationError(
                (
                    "Media conversion kind is missing "
                    f"for '{field_name}'."
                )
            )

        if not isinstance(
            raw_handoff_to_conversion,
            bool,
        ):
            raise ValidationError(
                (
                    "Content Safety handoff_to_conversion "
                    f"for '{field_name}' must be boolean."
                )
            )

        # Async pipeline v1 intentionally supports video only.
        # Future input types can be added centrally here.
        if input_type != SafetyInputType.VIDEO:
            raise ValidationError(
                (
                    "Asynchronous Content Safety currently "
                    f"supports video only: '{field_name}'."
                )
            )

        fields.append(
            ConfiguredMediaSafetyField(
                field_name=field_name,
                input_type=input_type,
                context=context,
                conversion_kind=conversion_kind,
                handoff_to_conversion=(
                    raw_handoff_to_conversion
                ),
            )
        )

    return fields

def _configured_media_safety_field(
    *,
    instance,
    field_name: str,
) -> ConfiguredMediaSafetyField | None:
    normalized_field = str(
        field_name
        or ""
    ).strip()

    if not normalized_field:
        return None

    for spec in configured_media_safety_fields(
        instance
    ):
        if spec.field_name == normalized_field:
            return spec

    return None


def content_safety_requires_conversion_handoff(
    *,
    instance,
    field_name: str,
) -> bool:
    """
    Return whether an approved safety generation must enter
    Media Conversion.

    Backward compatibility:
    - existing configured targets default to True
    - safety-only targets explicitly opt out
    """

    spec = _configured_media_safety_field(
        instance=instance,
        field_name=field_name,
    )

    if spec is None:
        raise ValidationError(
            "This media field is not configured for Content Safety."
        )

    return bool(
        spec.handoff_to_conversion
    )
    
def content_safety_allows_conversion_for_source(
    *,
    instance,
    field_name: str,
    kind: str,
    source_path: str,
) -> bool:
    """
    Authoritative field-level bridge from Content Safety to Media Conversion.

    Fields not configured for Content Safety are unaffected.

    A configured raw source can enter conversion only after the exact
    source generation has an ALLOW decision.
    """

    spec = _configured_media_safety_field(
        instance=instance,
        field_name=field_name,
    )

    if spec is None:
        return True

    normalized_kind = _enum_value(
        kind
    )

    if (
        normalized_kind
        != spec.conversion_kind
    ):
        logger.error(
            (
                "Content Safety / Media Conversion kind mismatch "
                "%s[%s].%s safety=%s conversion=%s"
            ),
            instance.__class__.__name__,
            getattr(
                instance,
                "pk",
                None,
            ),
            field_name,
            spec.conversion_kind,
            normalized_kind,
        )

        return False

    normalized_source = _clean_storage_key(
        source_path
    )

    if not normalized_source:
        return False

    # Converted artifacts are not new raw safety generations.
    if _is_final_media_source(
        instance=instance,
        conversion_kind=spec.conversion_kind,
        source_path=normalized_source,
    ):
        return True

    if not getattr(
        instance,
        "pk",
        None,
    ):
        return False

    target_ct = _target_content_type(
        instance
    )

    job = (
        ContentSafetyJob.objects
        .filter(
            content_type=target_ct,
            object_id=instance.pk,
            field_name=field_name,
        )
        .first()
    )

    if job is None:
        return False

    if (
        _clean_storage_key(
            job.source_path
        )
        != normalized_source
    ):
        # A Safety ALLOW decision from an older media generation
        # must never authorize a newer upload.
        return False

    if (
        job.decision
        != SafetyDecision.ALLOW
    ):
        return False

    if (
        job.status
        == ContentSafetyJobStatus.CANCELED
    ):
        return False

    return True


def resolve_content_safety_serializer_state(
    *,
    instance,
    field_name: str,
) -> dict | None:
    """
    Resolve owner-facing Content Safety state for one media field.

    Returns None when the field is not configured for asynchronous
    Content Safety.
    """

    spec = _configured_media_safety_field(
        instance=instance,
        field_name=field_name,
    )

    if spec is None:
        return None

    source_path = _current_source_path(
        instance,
        field_name,
    )

    if not source_path:
        return None

    if _is_final_media_source(
        instance=instance,
        conversion_kind=(
            spec.conversion_kind
        ),
        source_path=source_path,
    ):
        return None

    target_ct = _target_content_type(
        instance
    )

    job = (
        ContentSafetyJob.objects
        .filter(
            content_type=target_ct,
            object_id=instance.pk,
            field_name=field_name,
        )
        .order_by(
            "-updated_at",
            "-id",
        )
        .first()
    )

    if job is None:
        return {
            "required": True,
            "source_matches": False,
            "job_id": None,
            "status": "missing",
            "stage": "missing",
            "decision": None,
            "risk_level": None,
            "reason_code": None,
            "retryable": False,
            "can_retry": False,
            "progress": 0,
            "message": None,
            "conversion_job_id": None,
        }

    source_matches = (
        _clean_storage_key(
            job.source_path
        )
        == source_path
    )

    return {
        "required": True,
        "source_matches": source_matches,
        "job_id": str(
            job.public_id
        ),
        "status": str(
            job.status
        ),
        "stage": str(
            job.stage
        ),
        "decision": (
            str(
                job.decision
            )
            if job.decision
            else None
        ),
        "risk_level": (
            str(
                job.risk_level
            )
            if job.risk_level
            else None
        ),
        "reason_code": (
            str(
                job.reason_code
            )
            if job.reason_code
            else None
        ),
        "retryable": bool(
            job.retryable
        ),
        "can_retry": bool(
            job.can_retry
        ),
        "progress": int(
            job.progress
            or 0
        ),
        "message": (
            job.message
            or None
        ),
        "conversion_job_id": (
            job.conversion_job_id
        ),
    }

def current_content_safety_jobs(
    instance,
) -> list[ContentSafetyJob]:
    """
    Return jobs belonging to the currently attached media generation.
    """

    if not getattr(
        instance,
        "pk",
        None,
    ):
        return []

    target_ct = _target_content_type(
        instance
    )

    jobs: list[
        ContentSafetyJob
    ] = []

    for spec in configured_media_safety_fields(
        instance
    ):
        source_path = _current_source_path(
            instance,
            spec.field_name,
        )

        if not source_path:
            continue

        job = (
            ContentSafetyJob.objects
            .filter(
                content_type=target_ct,
                object_id=instance.pk,
                field_name=spec.field_name,
                source_path=source_path,
            )
            .first()
        )

        if job is not None:
            jobs.append(
                job
            )

    return jobs


def _dispatch_job(
    *,
    job_id: int,
    task_id: str,
) -> None:
    from apps.content_safety.tasks import (
        process_content_safety_media_job,
    )

    queue = str(
        getattr(
            settings,
            "CONTENT_SAFETY_VIDEO_QUEUE",
            "video",
        )
        or "video"
    ).strip()

    try:
        current = (
            ContentSafetyJob.objects
            .filter(
                pk=job_id,
                task_id=task_id,
                status=(
                    ContentSafetyJobStatus.QUEUED
                ),
            )
            .first()
        )

        if current is None:
            return

        process_content_safety_media_job.apply_async(
            kwargs={
                "job_id": job_id,
            },
            task_id=task_id,
            queue=queue,
        )

    except Exception as exc:
        logger.exception(
            (
                "Failed dispatching Content Safety "
                "job=%s task=%s"
            ),
            job_id,
            task_id,
        )

        ContentSafetyJob.objects.filter(
            pk=job_id,
            task_id=task_id,
            status=(
                ContentSafetyJobStatus.QUEUED
            ),
        ).update(
            status=(
                ContentSafetyJobStatus.FAILED
            ),
            stage=(
                ContentSafetyJobStage.FAILED
            ),
            retryable=True,
            progress=100,
            message=(
                "Could not start the safety check."
            ),
            error=str(
                exc
            ),
            heartbeat_at=timezone.now(),
            finished_at=timezone.now(),
        )


def _prepare_job_for_source(
    *,
    instance,
    actor,
    spec: ConfiguredMediaSafetyField,
    source_path: str,
    mime_type: str,
) -> ContentSafetyJob:
    target_ct = _target_content_type(
        instance
    )

    task_id = str(
        uuid.uuid4()
    )

    max_attempts = max(
        1,
        int(
            getattr(
                settings,
                "CONTENT_SAFETY_JOB_MAX_ATTEMPTS",
                3,
            )
            or 3
        ),
    )

    with transaction.atomic():
        job, created = (
            ContentSafetyJob.objects
            .get_or_create(
                content_type=target_ct,
                object_id=instance.pk,
                field_name=spec.field_name,
                defaults={
                    "actor": actor,
                    "input_type": spec.input_type,
                    "context": spec.context,
                    "source_path": source_path,
                    "mime_type": mime_type,
                    "status": (
                        ContentSafetyJobStatus.QUEUED
                    ),
                    "stage": (
                        ContentSafetyJobStage.QUEUED
                    ),
                    "progress": 0,
                    "message": (
                        "Waiting for safety review"
                    ),
                    "task_id": task_id,
                    "attempt": 1,
                    "max_attempts": max_attempts,
                    "heartbeat_at": timezone.now(),
                },
            )
        )

        if not created:
            job = (
                ContentSafetyJob.objects
                .select_for_update()
                .get(
                    pk=job.pk
                )
            )

            if (
                _clean_storage_key(
                    job.source_path
                )
                == source_path
            ):
                # Same source generation already has authoritative state.
                return job

            job.actor = actor
            job.input_type = spec.input_type
            job.context = spec.context
            job.source_path = source_path
            job.mime_type = mime_type

            job.input_hash = ""

            job.status = (
                ContentSafetyJobStatus.QUEUED
            )
            job.stage = (
                ContentSafetyJobStage.QUEUED
            )

            job.decision = ""
            job.risk_level = ""
            job.reason_code = ""

            job.retryable = False

            job.progress = 0
            job.message = (
                "Waiting for safety review"
            )
            job.error = ""

            job.task_id = task_id

            # New source = new safety generation.
            job.attempt = 1
            job.max_attempts = max_attempts

            job.conversion_job_id = None

            job.started_at = None
            job.finished_at = None
            job.heartbeat_at = timezone.now()

            job.save(
                update_fields=[
                    "actor",
                    "input_type",
                    "context",
                    "source_path",
                    "mime_type",
                    "input_hash",
                    "status",
                    "stage",
                    "decision",
                    "risk_level",
                    "reason_code",
                    "retryable",
                    "progress",
                    "message",
                    "error",
                    "task_id",
                    "attempt",
                    "max_attempts",
                    "conversion_job_id",
                    "started_at",
                    "finished_at",
                    "heartbeat_at",
                    "updated_at",
                ]
            )

        transaction.on_commit(
            lambda: _dispatch_job(
                job_id=job.pk,
                task_id=task_id,
            )
        )

    return job


def schedule_configured_content_safety_jobs(
    *,
    instance,
    actor,
    submitted_data: Mapping,
) -> list[ContentSafetyJob]:
    """
    Schedule Content Safety only for media fields supplied by this request.

    Must be called after serializer.save(), because the authoritative
    source path must already exist on persistent storage.
    """

    if not getattr(
        instance,
        "pk",
        None,
    ):
        raise ValidationError(
            "Content Safety target must be persisted first."
        )

    jobs: list[
        ContentSafetyJob
    ] = []

    for spec in configured_media_safety_fields(
        instance
    ):
        if spec.field_name not in submitted_data:
            continue

        submitted_file = submitted_data.get(
            spec.field_name
        )

        if not submitted_file:
            continue

        source_path = _current_source_path(
            instance,
            spec.field_name,
        )

        if not source_path:
            raise ValidationError(
                (
                    "The uploaded media was not persisted "
                    f"for '{spec.field_name}'."
                )
            )

        if not default_storage.exists(
            source_path
        ):
            raise ValidationError(
                (
                    "The uploaded media is unavailable "
                    f"for '{spec.field_name}'."
                )
            )

        mime_type = str(
            getattr(
                submitted_file,
                "content_type",
                None,
            )
            or mimetypes.guess_type(
                source_path
            )[0]
            or ""
        ).strip().lower()

        job = _prepare_job_for_source(
            instance=instance,
            actor=actor,
            spec=spec,
            source_path=source_path,
            mime_type=mime_type,
        )

        jobs.append(
            job
        )

    return jobs


def retry_content_safety_job(
    *,
    job: ContentSafetyJob,
    actor,
) -> ContentSafetyJob:
    """
    Retry an existing failed generation without re-uploading media.

    If Safety already returned ALLOW:
    - conversion-backed targets retry only Media Conversion handoff
    - safety-only targets retry only domain finalization

    Provider work is not repeated after an authoritative ALLOW.
    """

    actor_id = getattr(
        actor,
        "pk",
        None,
    )

    with transaction.atomic():
        locked = (
            ContentSafetyJob.objects
            .select_for_update()
            .select_related(
                "content_type",
            )
            .get(
                pk=job.pk
            )
        )

        if (
            not actor_id
            or locked.actor_id
            != actor_id
        ):
            raise ValidationError(
                "You cannot retry this safety check."
            )

        if (
            locked.status
            != ContentSafetyJobStatus.FAILED
        ):
            raise ValidationError(
                "Only failed safety checks can be retried."
            )

        if not locked.retryable:
            raise ValidationError(
                "This safety check cannot be retried."
            )

        if (
            locked.attempt
            >= locked.max_attempts
        ):
            raise ValidationError(
                "Maximum safety retry attempts reached."
            )

        target = locked.content_object

        if target is None:
            raise ValidationError(
                "The content no longer exists."
            )

        current_source = _current_source_path(
            target,
            locked.field_name,
        )

        expected_source = _clean_storage_key(
            locked.source_path
        )

        if (
            not current_source
            or current_source
            != expected_source
        ):
            raise ValidationError(
                "The source media has changed."
            )

        if not default_storage.exists(
            expected_source
        ):
            raise ValidationError(
                "The source media is no longer available."
            )

        task_id = str(
            uuid.uuid4()
        )

        already_approved = (
            locked.decision
            == SafetyDecision.ALLOW
        )

        handoff_to_conversion = (
            content_safety_requires_conversion_handoff(
                instance=target,
                field_name=locked.field_name,
            )
        )

        locked.status = (
            ContentSafetyJobStatus.QUEUED
        )

        locked.stage = (
            ContentSafetyJobStage.QUEUED
        )

        locked.retryable = False
        locked.progress = 0

        if already_approved:
            locked.message = (
                "Preparing video processing"
                if handoff_to_conversion
                else "Finalizing safety approval"
            )
        else:
            locked.message = (
                "Waiting for safety review"
            )

        locked.error = ""
        locked.task_id = task_id
        locked.attempt += 1

        locked.conversion_job_id = None

        locked.started_at = None
        locked.finished_at = None
        locked.heartbeat_at = timezone.now()

        if not already_approved:
            locked.decision = ""
            locked.risk_level = ""
            locked.reason_code = ""
            locked.input_hash = ""

        locked.save(
            update_fields=[
                "status",
                "stage",
                "decision",
                "risk_level",
                "reason_code",
                "input_hash",
                "retryable",
                "progress",
                "message",
                "error",
                "task_id",
                "attempt",
                "conversion_job_id",
                "started_at",
                "finished_at",
                "heartbeat_at",
                "updated_at",
            ]
        )

        transaction.on_commit(
            lambda: _dispatch_job(
                job_id=locked.pk,
                task_id=task_id,
            )
        )

    return locked


def _matching_conversion_job(
    *,
    instance,
    spec: ConfiguredMediaSafetyField,
    source_path: str,
) -> MediaConversionJob | None:
    target_ct = _target_content_type(
        instance
    )

    normalized_source = _clean_storage_key(
        source_path
    )

    if not normalized_source:
        return None

    return (
        MediaConversionJob.objects
        .filter(
            content_type=target_ct,
            object_id=instance.pk,
            field_name=spec.field_name,
            kind=spec.conversion_kind,
            source_path=normalized_source,
        )
        .order_by(
            "-updated_at",
            "-id",
        )
        .first()
    )


def try_handoff_approved_media_to_conversion(
    *,
    job: ContentSafetyJob,
) -> MediaConversionJob:
    """
    Hand one approved field generation to the existing Media Conversion
    pipeline and return its authoritative conversion job.

    Safety-only targets must never enter this function.
    """

    target = job.content_object

    if target is None:
        raise ValidationError(
            "The content no longer exists."
        )

    spec = _configured_media_safety_field(
        instance=target,
        field_name=job.field_name,
    )

    if spec is None:
        raise ValidationError(
            "This media field is not configured for Content Safety."
        )

    if not spec.handoff_to_conversion:
        raise ValidationError(
            (
                "This Content Safety field is safety-only "
                "and does not use Media Conversion."
            )
        )

    source_path = _current_source_path(
        target,
        job.field_name,
    )

    expected_source = _clean_storage_key(
        job.source_path
    )

    if (
        not source_path
        or source_path
        != expected_source
    ):
        raise ValidationError(
            "The source media has changed."
        )

    if (
        job.decision
        != SafetyDecision.ALLOW
    ):
        raise ValidationError(
            "Media has not passed Content Safety."
        )

    converter = getattr(
        target,
        "convert_uploaded_media_async",
        None,
    )

    if not callable(
        converter
    ):
        raise RuntimeError(
            "Target does not support media conversion."
        )

    # Conversion-backed targets keep the existing behavior.
    converter()

    conversion_job = _matching_conversion_job(
        instance=target,
        spec=spec,
        source_path=expected_source,
    )

    if conversion_job is None:
        raise RuntimeError(
            "No matching MediaConversionJob was created."
        )

    if conversion_job.status in {
        MediaJobStatus.FAILED,
        MediaJobStatus.CANCELED,
    }:
        raise RuntimeError(
            (
                "Media Conversion did not accept the handoff. "
                f"Job status: {conversion_job.status}"
            )
        )

    return conversion_job