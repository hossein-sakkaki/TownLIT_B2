# apps/media_conversion/services/serializer_gate.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.contrib.contenttypes.models import (
    ContentType,
)

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobStatus,
)


@dataclass
class MediaGateState:
    ready: bool
    status: str

    phase: str

    processing: bool

    job_id: Optional[int] = None

    content_safety: Optional[dict] = None


def _current_media_source(
    obj,
    field_name: str,
) -> str:
    value = getattr(
        obj,
        field_name,
        None,
    )

    return str(
        getattr(
            value,
            "name",
            "",
        )
        or ""
    ).strip().lstrip(
        "/"
    )


def _get_job_for(
    obj,
    field_name: str,
) -> Optional[MediaConversionJob]:
    """
    While media is unconverted, match the current raw source generation.

    Once conversion is complete the model field may already point to a
    generated artifact such as master.m3u8, while MediaConversionJob keeps
    the original raw source_path. In that state the latest field job is used.
    """

    ct = ContentType.objects.get_for_model(
        obj.__class__,
        for_concrete_model=False,
    )

    qs = (
        MediaConversionJob.objects
        .filter(
            content_type=ct,
            object_id=obj.id,
            field_name=field_name,
        )
        .order_by(
            "-updated_at",
            "-id",
        )
    )

    if (
        getattr(
            obj,
            "is_converted",
            False,
        )
        is not True
    ):
        source_path = _current_media_source(
            obj,
            field_name,
        )

        if source_path:
            exact = (
                qs
                .filter(
                    source_path=source_path
                )
                .first()
            )

            if exact is not None:
                return exact

            return None

    return qs.first()


def _resolve_content_safety_state(
    obj,
    field_name: str,
) -> Optional[dict]:
    """
    Resolve Content Safety through an optional model capability.

    Media Conversion intentionally has no direct dependency on
    apps.content_safety.
    """

    resolver = getattr(
        obj,
        "get_media_content_safety_gate",
        None,
    )

    if not callable(
        resolver
    ):
        return None

    try:
        state = resolver(
            field_name=field_name,
        )

    except Exception:
        # Fail closed for an opted-in target.
        return {
            "required": True,
            "source_matches": False,
            "job_id": None,
            "status": "unavailable",
            "stage": "failed",
            "decision": None,
            "risk_level": None,
            "reason_code": None,
            "retryable": False,
            "can_retry": False,
            "progress": 0,
            "message": None,
            "conversion_job_id": None,
        }

    return (
        state
        if isinstance(
            state,
            dict,
        )
        else None
    )


def _safety_gate_state(
    safety: dict,
) -> Optional[MediaGateState]:
    """
    Return a blocking/pending Safety state.

    Return None only when Safety has already ALLOWed this exact source
    and Media Conversion should become authoritative.
    """

    if not safety.get(
        "source_matches",
        False,
    ):
        return MediaGateState(
            ready=False,
            status="safety_missing",
            phase="content_safety",
            processing=False,
            content_safety=safety,
        )

    status = str(
        safety.get(
            "status"
        )
        or ""
    ).strip().lower()

    stage = str(
        safety.get(
            "stage"
        )
        or ""
    ).strip().lower()

    decision = str(
        safety.get(
            "decision"
        )
        or ""
    ).strip().lower()

    if decision == "block":
        return MediaGateState(
            ready=False,
            status="safety_blocked",
            phase="content_safety",
            processing=False,
            content_safety=safety,
        )

    if decision == "review":
        return MediaGateState(
            ready=False,
            status="safety_review",
            phase="content_safety",
            processing=False,
            content_safety=safety,
        )

    if (
        status == "failed"
        and decision == "allow"
    ):
        return MediaGateState(
            ready=False,
            status="safety_handoff_failed",
            phase="handoff",
            processing=False,
            content_safety=safety,
        )

    if status == "failed":
        return MediaGateState(
            ready=False,
            status="safety_failed",
            phase="content_safety",
            processing=False,
            content_safety=safety,
        )

    if status == "canceled":
        return MediaGateState(
            ready=False,
            status="safety_canceled",
            phase="content_safety",
            processing=False,
            content_safety=safety,
        )

    # ALLOW is the authoritative permission for the exact raw source.
    #
    # During HANDOFF the conversion job may not yet be observable.
    if decision == "allow":
        if status in {
            "queued",
            "processing",
        }:
            return MediaGateState(
                ready=False,
                status="safety_handoff",
                phase="handoff",
                processing=True,
                content_safety=safety,
            )

        # DONE + ALLOW means Safety is complete.
        # Media Conversion becomes authoritative below.
        return None

    if status == "queued":
        return MediaGateState(
            ready=False,
            status="safety_queued",
            phase="content_safety",
            processing=True,
            content_safety=safety,
        )

    if status == "processing":
        return MediaGateState(
            ready=False,
            status="safety_processing",
            phase="content_safety",
            processing=True,
            content_safety=safety,
        )

    if status == "done":
        # Defensive fallback for an invalid terminal Safety result.
        return MediaGateState(
            ready=False,
            status="safety_unresolved",
            phase="content_safety",
            processing=False,
            content_safety=safety,
        )

    return MediaGateState(
        ready=False,
        status="safety_pending",
        phase="content_safety",
        processing=True,
        content_safety=safety,
    )


def _media_job_is_processing(
    job: MediaConversionJob,
) -> bool:
    return job.status in {
        MediaJobStatus.QUEUED,
        MediaJobStatus.PROCESSING,
    }


def _compute_gate_state(
    obj,
    field_name: str,
    require_job: bool,
) -> MediaGateState:
    """
    Resolve the complete media readiness pipeline:

    Content Safety -> Media Conversion -> Ready
    """

    is_converted = (
        getattr(
            obj,
            "is_converted",
            False,
        )
        is True
    )

    # Content Safety is a pre-conversion gate.
    #
    # Do not retroactively hide already-converted legacy media simply
    # because it predates ContentSafetyJob.
    if not is_converted:
        safety = _resolve_content_safety_state(
            obj,
            field_name,
        )

        if safety is not None:
            safety_state = _safety_gate_state(
                safety
            )

            if safety_state is not None:
                return safety_state

    job = _get_job_for(
        obj,
        field_name,
    )

    if (
        not job
        and require_job
    ):
        return MediaGateState(
            ready=False,
            status="missing_job",
            phase="media_conversion",
            processing=False,
            job_id=None,
        )

    if not is_converted:
        if job is None:
            return MediaGateState(
                ready=False,
                status="missing_job",
                phase="media_conversion",
                processing=False,
                job_id=None,
            )

        return MediaGateState(
            ready=False,
            status=str(
                job.status
            ),
            phase="media_conversion",
            processing=(
                _media_job_is_processing(
                    job
                )
            ),
            job_id=job.id,
        )

    if job:
        if (
            job.status
            == MediaJobStatus.DONE
        ):
            return MediaGateState(
                ready=True,
                status="done",
                phase="ready",
                processing=False,
                job_id=job.id,
            )

        return MediaGateState(
            ready=False,
            status=str(
                job.status
            ),
            phase="media_conversion",
            processing=(
                _media_job_is_processing(
                    job
                )
            ),
            job_id=job.id,
        )

    return MediaGateState(
        ready=True,
        status="done",
        phase="ready",
        processing=False,
        job_id=None,
    )


def _strip_media_keys(
    data: Dict[str, Any],
    field_name: str,
) -> None:
    """
    Remove media delivery keys before the field is ready.
    """

    data.pop(
        field_name,
        None,
    )

    data.pop(
        f"{field_name}_key",
        None,
    )

    data.pop(
        f"{field_name}_signed_url",
        None,
    )

    data.pop(
        "thumbnail",
        None,
    )

    data.pop(
        "thumbnail_key",
        None,
    )

    data.pop(
        "thumbnail_signed_url",
        None,
    )


def _build_pipeline_payload(
    state: MediaGateState,
) -> dict:
    payload = {
        "phase": state.phase,
        "status": state.status,
        "processing": state.processing,
        "conversion_job_id": (
            state.job_id
        ),
    }

    if state.content_safety is not None:
        payload[
            "content_safety"
        ] = state.content_safety

    return payload


def gate_media_payload(
    *,
    obj,
    data: Dict[str, Any],
    viewer=None,
    field_name: str,
    require_job: bool = True,
    include_job_target: bool = True,
) -> Dict[str, Any]:
    state = _compute_gate_state(
        obj,
        field_name=field_name,
        require_job=require_job,
    )

    # Always expose one shared pipeline contract.
    data[
        "media_pipeline"
    ] = _build_pipeline_payload(
        state
    )

    if state.ready:
        return data

    _strip_media_keys(
        data,
        field_name,
    )

    # Backward-compatible fields.
    #
    # "converting" now means active media pipeline work for legacy
    # consumers. It is false for blocked/review/failed states.
    data[
        "converting"
    ] = state.processing

    data[
        "ready_status"
    ] = state.status

    # This remains strictly MediaConversionJob.id.
    # ContentSafetyJob uses its public UUID inside media_pipeline.
    data[
        "job_id"
    ] = state.job_id

    if include_job_target:
        ct = ContentType.objects.get_for_model(
            obj.__class__,
            for_concrete_model=False,
        )

        data[
            "job_target"
        ] = {
            "content_type_model": (
                f"{ct.app_label}.{ct.model}"
            ),
            "content_type_id": ct.id,
            "object_id": obj.id,
            "field_name": field_name,
        }

    return data