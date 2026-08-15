# apps/posts/services/journeys/processing.py

from __future__ import annotations

import logging
import json

from collections.abc import Mapping

from django.core.serializers.json import DjangoJSONEncoder
from celery import current_app
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)
from apps.creative_editor.services.compositions import request_render
from apps.journey_insights.services.daily_prompt import (
    resolve_daily_reflection_after_publish,
)
from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobKind,
    MediaJobStatus,
)
from apps.media_conversion.services.jobs import upsert_job
from apps.media_conversion.services.progress import touch_job
from apps.media_conversion.services.workflows import enqueue_workflow_job
from apps.posts.services.journeys.publish import publish_journey_entry
from apps.profiles.models.member import Member
from apps.creative_editor.models import (
    CreativeComposition,
    CreativeCompositionMedia,
    CreativeRenderJob,
)

from apps.creative_editor.services.document import (
    extract_document_references,
)

logger = logging.getLogger(__name__)

JOURNEY_WORKFLOW_FIELD = "journey_publish"
JOURNEY_WORKFLOW_HANDLER = "apps.posts.services.journeys.processing"
JOURNEY_WORKFLOW_QUEUE = "video"

JOURNEY_STAGE_PLAN = [
    {
        "key": "preparing",
        "label": "Preparing Media",
        "weight": 10,
    },
    {
        "key": "rendering",
        "label": "Rendering Journey",
        "weight": 75,
    },
    {
        "key": "publishing",
        "label": "Publishing Journey",
        "weight": 15,
    },
]


def _json_value(value):
    if value is None:
        return None
    return str(value)

def _json_safe(value):
    """
    Normalize nested workflow payload values for JSONField storage.

    DjangoJSONEncoder safely handles UUID, datetime, date,
    Decimal and other Django-compatible JSON values while
    preserving normal dict/list/bool/number structures.
    """
    return json.loads(
        json.dumps(
            value,
            cls=DjangoJSONEncoder,
        )
    )
    
def _content_safety_scalar_text(
    value,
) -> str:
    """
    Resolve DRF ErrorDetail / nested full-detail values
    into one plain string.
    """

    if value is None:
        return ""

    if isinstance(
        value,
        Mapping,
    ):
        for key in (
            "message",
            "value",
            "detail",
        ):
            if key in value:
                resolved = (
                    _content_safety_scalar_text(
                        value[key]
                    )
                )

                if resolved:
                    return resolved

        return ""

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        for item in value:
            resolved = (
                _content_safety_scalar_text(
                    item
                )
            )

            if resolved:
                return resolved

        return ""

    return str(
        value
    ).strip()


def _content_safety_bool(
    value,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    normalized = (
        _content_safety_scalar_text(
            value
        )
        .strip()
        .lower()
    )

    return normalized in {
        "1",
        "true",
        "yes",
        "on",
    }


def _find_content_safety_payload(
    value,
) -> Mapping | None:
    """
    Find TownLIT's structured Content Safety payload
    inside a DRF exception detail tree.
    """

    if isinstance(
        value,
        Mapping,
    ):
        code = (
            _content_safety_scalar_text(
                value.get(
                    "code"
                )
            )
        )

        if code.startswith(
            "content_safety_"
        ):
            return value

        error_payload = value.get(
            "error"
        )

        found = (
            _find_content_safety_payload(
                error_payload
            )
        )

        if found is not None:
            return found

        for nested in value.values():
            found = (
                _find_content_safety_payload(
                    nested
                )
            )

            if found is not None:
                return found

        return None

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        for nested in value:
            found = (
                _find_content_safety_payload(
                    nested
                )
            )

            if found is not None:
                return found

    return None


def _extract_content_safety_failure(
    exc: Exception,
) -> dict | None:
    """
    Extract TownLIT's normal structured Content Safety error
    without parsing exception strings.

    This keeps async Journey failures compatible with the same
    iOS ContentSafetyErrorResolver used by synchronous requests.
    """

    candidates = []

    detail = getattr(
        exc,
        "detail",
        None,
    )

    if detail is not None:
        candidates.append(
            detail
        )

    full_details = getattr(
        exc,
        "get_full_details",
        None,
    )

    if callable(
        full_details
    ):
        try:
            candidates.append(
                full_details()
            )
        except Exception:
            pass

    for candidate in candidates:
        payload = (
            _find_content_safety_payload(
                candidate
            )
        )

        if payload is None:
            continue

        code = (
            _content_safety_scalar_text(
                payload.get(
                    "code"
                )
            )
        )

        if not code.startswith(
            "content_safety_"
        ):
            continue

        retryable = (
            _content_safety_bool(
                payload.get(
                    "retryable"
                )
            )
        )

        decision = (
            _content_safety_scalar_text(
                payload.get(
                    "decision"
                )
            )
            .strip()
            .lower()
        )

        if not decision:
            decision = (
                "review"
                if retryable
                else "block"
            )

        reason_code = (
            _content_safety_scalar_text(
                payload.get(
                    "reason_code"
                )
            )
            .strip()
            .lower()
        )

        if not reason_code:
            reason_code = (
                "provider_unavailable"
                if retryable
                else "provider_flagged"
            )

        return {
            "code": code,
            "decision": decision,
            "reason_code": reason_code,
            "retryable": retryable,
        }

    return None


def _mark_journey_content_safety_failure(
    *,
    job: MediaConversionJob,
    payload: dict,
    exc: Exception,
) -> bool:
    """
    Convert an async Content Safety rejection into a terminal
    Journey workflow failure while preserving its structured
    error payload for iOS.

    Returns True only when the exception was a Content Safety
    failure and was handled here.
    """

    failure = (
        _extract_content_safety_failure(
            exc
        )
    )

    if failure is None:
        return False

    updated_payload = dict(
        payload
        or {}
    )

    updated_payload[
        "content_safety_failure"
    ] = failure

    job.payload = _json_safe(
        updated_payload
    )

    job.save(
        update_fields=[
            "payload",
            "updated_at",
        ]
    )

    
    #  Content Safety rejection is terminal for this revision.
    #  The draft/composition itself remains intact and editable.
    job.mark_failed(
        "Journey did not pass TownLIT Content Safety."
    )

    return True
    
@transaction.atomic
def submit_journey_workflow(
    *,
    user,
    owner,
    validated_data: dict,
) -> tuple[MediaConversionJob, bool]:
    if not user or not user.is_authenticated:
        raise ValidationError("Authentication is required.")

    if not isinstance(owner, Member) or owner.user_id != user.pk:
        raise ValidationError(
            {"owner": "A valid Member owner is required."}
        )

    composition = (
        CreativeComposition.objects
        .select_for_update()
        .filter(
            public_id=validated_data["composition_id"],
            owner=user,
            is_active=True,
        )
        .first()
    )

    if composition is None:
        raise ValidationError(
            {"composition_id": "Composition was not found."}
        )

    revision = int(validated_data["composition_revision"])

    if composition.revision != revision:
        raise ValidationError(
            {"composition_revision": "Composition revision changed."}
        )

    payload = {
        "owner_id": owner.pk,
        "composition_id": str(composition.public_id),
        "composition_revision": revision,
        "visibility": validated_data["visibility"],
        "retention_policy": validated_data["retention_policy"],
        "timezone": validated_data.get("timezone") or None,
        "music_track_id": _json_value(
            validated_data.get("music_track_id")
        ),
        "music_variant_id": _json_value(
            validated_data.get("music_variant_id")
        ),
        "music_clip_start_ms": validated_data.get(
            "music_clip_start_ms"
        ),
        "music_clip_end_ms": validated_data.get(
            "music_clip_end_ms"
        ),
        "music_volume": _json_value(
            validated_data.get("music_volume", 1)
        ),
    }

    ct = ContentType.objects.get_for_model(
        CreativeComposition,
        for_concrete_model=False,
    )

    existing = (
        MediaConversionJob.objects
        .select_for_update()
        .filter(
            content_type=ct,
            object_id=composition.pk,
            field_name=JOURNEY_WORKFLOW_FIELD,
        )
        .first()
    )

    if existing is not None:
        existing_revision = int(
            (existing.payload or {}).get(
                "composition_revision",
                0,
            )
            or 0
        )

        if existing_revision == revision:
            return existing, False

        if existing.status in {
            MediaJobStatus.QUEUED,
            MediaJobStatus.PROCESSING,
        }:
            raise ValidationError(
                {
                    "composition_revision": (
                        "Another Journey submission is already "
                        "processing for this composition."
                    ),
                }
            )

    job = upsert_job(
        composition,
        JOURNEY_WORKFLOW_FIELD,
        MediaJobKind.WORKFLOW,
        status=MediaJobStatus.QUEUED,
        queue=JOURNEY_WORKFLOW_QUEUE,
        message="Queued for Journey processing",
        workflow_handler=JOURNEY_WORKFLOW_HANDLER,
        payload=payload,
    )

    transaction.on_commit(
        lambda: enqueue_workflow_job(job)
    )

    return job, True


def _resolve_pending_composition_media(
    composition: CreativeComposition,
) -> tuple[
    list[CreativeCompositionMedia],
    list[MediaConversionJob],
]:
    references = extract_document_references(
        composition.document or {}
    )

    media_ids = references.media_public_ids

    if not media_ids:
        return [], []

    media_items = list(
        CreativeCompositionMedia.objects
        .filter(
            composition=composition,
            public_id__in=media_ids,
            is_active=True,
        )
        .order_by(
            "created_at",
            "id",
        )
    )

    pending_media = [
        media
        for media in media_items
        if not media.is_available()
    ]

    if not pending_media:
        return [], []

    media_ct = ContentType.objects.get_for_model(
        CreativeCompositionMedia,
        for_concrete_model=False,
    )

    jobs = list(
        MediaConversionJob.objects
        .filter(
            content_type=media_ct,
            object_id__in=[
                media.pk
                for media in pending_media
            ],
        )
        .order_by(
            "-updated_at",
            "-id",
        )
    )

    return pending_media, jobs

def run_workflow(job: MediaConversionJob) -> None:
    job.refresh_from_db()

    if job.status != MediaJobStatus.PROCESSING:
        return

    payload = dict(job.payload or {})

    composition = (
        CreativeComposition.objects
        .select_related("owner")
        .filter(pk=job.object_id)
        .first()
    )

    if composition is None:
        raise ValidationError("Composition no longer exists.")

    revision = int(
        payload.get("composition_revision") or 0
    )

    if composition.revision != revision:
        raise ValidationError(
            "Composition changed after Journey submission."
        )

    owner = (
        Member.objects
        .filter(
            pk=payload.get("owner_id"),
            user_id=composition.owner_id,
            is_active=True,
        )
        .first()
    )

    if owner is None:
        raise ValidationError("Journey owner is unavailable.")

    pending_media, media_jobs = (
        _resolve_pending_composition_media(
            composition
        )
    )

    if pending_media:
        jobs_by_object_id = {
            job.object_id: job
            for job in media_jobs
        }

        for media in pending_media:
            conversion_job = jobs_by_object_id.get(
                media.pk
            )

            if conversion_job is None:
                continue

            if conversion_job.status == MediaJobStatus.FAILED:
                raise ValidationError(
                    conversion_job.error
                    or "Journey source media processing failed."
                )

            if conversion_job.status == MediaJobStatus.CANCELED:
                raise ValidationError(
                    "Journey source media processing was canceled."
                )

        active_jobs = [
            job
            for job in media_jobs
            if job.status in {
                MediaJobStatus.QUEUED,
                MediaJobStatus.PROCESSING,
            }
        ]

        progress_values = [
            int(job.progress or 0)
            for job in active_jobs
        ]

        media_progress = (
            sum(progress_values)
            / len(progress_values)
            if progress_values
            else 0
        )

        touch_job(
            job,
            status=MediaJobStatus.PROCESSING,
            stage_plan=JOURNEY_STAGE_PLAN,
            stage="preparing",
            stage_index=0,
            stage_progress=max(
                0.0,
                min(
                    0.99,
                    media_progress / 100.0,
                ),
            ),
            message="Preparing Journey media",
        )

        enqueue_workflow_job(
            job,
            countdown=2,
        )

        return

    render_result = request_render(
        composition=composition,
        allow_requeue_canceled=True,
    )

    render_job = render_result.job

    payload["render_job_id"] = render_job.pk
    payload["render_job_public_id"] = str(
        render_job.public_id
    )

    MediaConversionJob.objects.filter(
        pk=job.pk
    ).update(
        payload=_json_safe(payload),
        updated_at=timezone.now(),
    )

    render_job.refresh_from_db()

    if render_job.status in {
        CreativeRenderJob.Status.QUEUED,
        CreativeRenderJob.Status.PROCESSING,
    }:
        touch_job(
            job,
            status=MediaJobStatus.PROCESSING,
            stage_plan=JOURNEY_STAGE_PLAN,
            stage="rendering",
            stage_index=1,
            stage_progress=max(
                0.0,
                min(
                    0.99,
                    float(render_job.progress or 0) / 100.0,
                ),
            ),
            message=render_job.message or "Rendering Journey",
        )

        enqueue_workflow_job(
            job,
            countdown=2,
        )
        return

    if render_job.status == CreativeRenderJob.Status.FAILED:
        raise ValidationError(
            render_job.error or "Journey render failed."
        )

    if render_job.status == CreativeRenderJob.Status.CANCELED:
        raise ValidationError("Journey render was canceled.")

    if render_job.status != CreativeRenderJob.Status.DONE:
        raise ValidationError(
            "Journey render entered an invalid state."
        )

    touch_job(
        job,
        stage_plan=JOURNEY_STAGE_PLAN,
        stage="publishing",
        stage_index=2,
        stage_progress=0.05,
        message="Publishing Journey",
    )

    try:
        result = publish_journey_entry(
            user=composition.owner,
            owner=owner,
            composition_id=composition.public_id,
            render_job_id=render_job.public_id,
            composition_revision=revision,
            visibility=payload["visibility"],
            retention_policy=payload["retention_policy"],
            requested_timezone=payload.get(
                "timezone"
            ),
            music_track_id=payload.get(
                "music_track_id"
            ),
            music_variant_id=payload.get(
                "music_variant_id"
            ),
            music_clip_start_ms=payload.get(
                "music_clip_start_ms"
            ),
            music_clip_end_ms=payload.get(
                "music_clip_end_ms"
            ),
            music_volume=payload.get(
                "music_volume",
                "1",
            ),
        )

    except Exception as exc:
        handled_content_safety = (
            _mark_journey_content_safety_failure(
                job=job,
                payload=payload,
                exc=exc,
            )
        )

        if handled_content_safety:
            logger.info(
                "journey.workflow.content_safety_rejected",
                extra={
                    "job_id": job.pk,
                    "composition_id": composition.pk,
                    "revision": revision,
                },
            )

            return

        raise

    reflection = None

    try:
        reflection = resolve_daily_reflection_after_publish(
            user=composition.owner,
            journey=result.journey,
            entry=result.entry,
        ).as_dict()
    except Exception:
        logger.exception(
            "journey.workflow.reflection_failed",
            extra={
                "job_id": job.pk,
                "entry_id": result.entry.pk,
            },
        )

    payload["result"] = {
        "journey_id": result.journey.pk,
        "journey_slug": result.journey.slug,
        "entry_id": result.entry.pk,
        "entry_slug": result.entry.slug,
        "created_journey": result.created_journey,
        "daily_reflection": reflection,
    }

    job.payload = _json_safe(payload)
    job.save(
        update_fields=[
            "payload",
            "updated_at",
        ]
    )

    touch_job(
        job,
        stage_plan=JOURNEY_STAGE_PLAN,
        stage="publishing",
        stage_index=2,
        stage_progress=1.0,
        message="Journey ready",
    )

    job.refresh_from_db()
    job.mark_done(msg="Journey ready")


def cancel_workflow(job: MediaConversionJob) -> None:
    payload = dict(job.payload or {})
    render_job = None

    render_job_id = payload.get("render_job_id")

    if render_job_id:
        render_job = (
            CreativeRenderJob.objects
            .filter(pk=render_job_id)
            .first()
        )

    if render_job is None:
        composition = (
            CreativeComposition.objects
            .filter(pk=job.object_id)
            .first()
        )

        revision = int(
            payload.get("composition_revision") or 0
        )

        if composition is not None:
            render_job = (
                CreativeRenderJob.objects
                .filter(
                    composition=composition,
                    requested_revision=revision,
                )
                .first()
            )

    if (
        render_job is None
        or render_job.status
        not in {
            CreativeRenderJob.Status.QUEUED,
            CreativeRenderJob.Status.PROCESSING,
        }
    ):
        return

    if render_job.task_id:
        try:
            current_app.control.revoke(
                render_job.task_id,
                terminate=False,
            )
        except Exception:
            pass

    render_job.mark_canceled(
        "Journey processing canceled"
    )

    CreativeComposition.objects.filter(
        pk=render_job.composition_id,
        revision=render_job.requested_revision,
        status=CreativeComposition.Status.RENDERING,
    ).update(
        status=CreativeComposition.Status.DRAFT,
        render_error="",
        updated_at=timezone.now(),
    )