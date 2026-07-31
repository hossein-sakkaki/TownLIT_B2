# apps/creative_editor/services/compositions.py

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.creative_editor.constants import (
    CREATIVE_RENDER_QUEUE,
)
from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)
from apps.creative_editor.services.document import (
    validate_document_references,
)


class CreativeRevisionConflict(Exception):
    """
    Raised when the client edits an outdated revision.
    """

    def __init__(
        self,
        *,
        expected_revision: int,
        current_revision: int,
    ):
        self.expected_revision = expected_revision
        self.current_revision = current_revision

        super().__init__(
            (
                "Composition revision conflict. "
                f"Expected {expected_revision}, "
                f"current revision is {current_revision}."
            )
        )


@dataclass(frozen=True)
class CompositionUpdateResult:
    composition: CreativeComposition
    document_changed: bool


@dataclass(frozen=True)
class RenderRequestResult:
    job: CreativeRenderJob
    created: bool


def canonical_document_hash(
    document: dict,
) -> str:
    """
    Build a deterministic document hash.
    """

    payload = json.dumps(
        document or {},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def create_composition(
    *,
    owner,
    validated_data: dict,
) -> CreativeComposition:
    """
    Create a validated editor composition.
    """

    document = copy.deepcopy(
        validated_data.get("document") or {}
    )

    validate_document_references(
        document
    )

    composition = CreativeComposition(
        owner=owner,
        **validated_data,
    )

    composition.document = document

    composition.document_sha256 = (
        canonical_document_hash(
            document
        )
    )

    composition.full_clean()
    composition.save()

    return composition


@transaction.atomic
def update_composition(
    *,
    composition: CreativeComposition,
    expected_revision: int,
    validated_data: dict,
) -> CompositionUpdateResult:
    """
    Update one composition with optimistic locking.
    """

    locked = (
        CreativeComposition.objects
        .select_for_update()
        .get(pk=composition.pk)
    )

    if locked.revision != expected_revision:
        raise CreativeRevisionConflict(
            expected_revision=expected_revision,
            current_revision=locked.revision,
        )

    incoming_document = validated_data.pop(
        "document",
        None,
    )

    document_changed = False

    if incoming_document is not None:
        incoming_document = copy.deepcopy(
            incoming_document
        )

        validate_document_references(
            incoming_document
        )

        incoming_hash = (
            canonical_document_hash(
                incoming_document
            )
        )

        document_changed = (
            incoming_hash
            != locked.document_sha256
        )

        if document_changed:
            locked.document = (
                incoming_document
            )

            locked.document_sha256 = (
                incoming_hash
            )

            locked.revision += 1

            # Invalidate the previous render.
            locked.status = (
                CreativeComposition.Status.DRAFT
            )

            locked.render_error = ""

    for field_name, value in (
        validated_data.items()
    ):
        setattr(
            locked,
            field_name,
            value,
        )

    locked.full_clean()
    locked.save()

    return CompositionUpdateResult(
        composition=locked,
        document_changed=document_changed,
    )


def _enqueue_render_job(
    *,
    job_id: int,
) -> None:
    """
    Dispatch the committed render job.
    """

    from apps.creative_editor.tasks.render import (
        render_creative_composition_task,
    )

    result = (
        render_creative_composition_task
        .apply_async(
            kwargs={
                "render_job_id": job_id,
            },
            queue=CREATIVE_RENDER_QUEUE,
        )
    )

    CreativeRenderJob.objects.filter(
        pk=job_id
    ).update(
        task_id=str(
            result.id or ""
        ),
        queue=CREATIVE_RENDER_QUEUE,
        updated_at=timezone.now(),
    )


@transaction.atomic
def request_render(
    *,
    composition: CreativeComposition,
) -> RenderRequestResult:
    """
    Create or return a render job for the current revision.
    """

    locked = (
        CreativeComposition.objects
        .select_for_update()
        .get(pk=composition.pk)
    )

    if not locked.is_active:
        raise ValidationError(
            (
                "Archived or inactive compositions "
                "cannot be rendered."
            )
        )

    validate_document_references(
        locked.document
    )

    existing = (
        CreativeRenderJob.objects
        .filter(
            composition=locked,
            requested_revision=(
                locked.revision
            ),
        )
        .first()
    )

    if existing is not None:
        should_requeue = (
            existing.status
            == CreativeRenderJob.Status.FAILED
            and existing.attempt
            < existing.max_attempts
        )

        if should_requeue:
            existing.status = (
                CreativeRenderJob.Status.QUEUED
            )
            existing.progress = 0
            existing.stage = "queued"
            existing.message = (
                "Queued for rendering"
            )
            existing.error = ""
            existing.finished_at = None
            existing.duration_ms = None
            existing.heartbeat_at = (
                timezone.now()
            )

            existing.save(
                update_fields=[
                    "status",
                    "progress",
                    "stage",
                    "message",
                    "error",
                    "finished_at",
                    "duration_ms",
                    "heartbeat_at",
                    "updated_at",
                ]
            )

            transaction.on_commit(
                lambda: _enqueue_render_job(
                    job_id=existing.pk
                )
            )

        return RenderRequestResult(
            job=existing,
            created=False,
        )

    job = CreativeRenderJob.objects.create(
        composition=locked,
        requested_revision=locked.revision,
        document_snapshot=copy.deepcopy(
            locked.document
        ),
        document_sha256=(
            locked.document_sha256
        ),
        status=(
            CreativeRenderJob.Status.QUEUED
        ),
        progress=0,
        stage="queued",
        message="Queued for rendering",
        heartbeat_at=timezone.now(),
        queue=CREATIVE_RENDER_QUEUE,
    )

    locked.status = (
        CreativeComposition.Status.RENDERING
    )

    locked.render_error = ""

    locked.save(
        update_fields=[
            "status",
            "render_error",
            "updated_at",
        ]
    )

    transaction.on_commit(
        lambda: _enqueue_render_job(
            job_id=job.pk
        )
    )

    return RenderRequestResult(
        job=job,
        created=True,
    )


@transaction.atomic
def archive_composition(
    *,
    composition: CreativeComposition,
) -> CreativeComposition:
    """
    Soft archive a composition.
    """

    locked = (
        CreativeComposition.objects
        .select_for_update()
        .get(pk=composition.pk)
    )

    locked.status = (
        CreativeComposition.Status.ARCHIVED
    )

    locked.is_active = False

    locked.save(
        update_fields=[
            "status",
            "is_active",
            "updated_at",
        ]
    )

    CreativeRenderJob.objects.filter(
        composition=locked,
        status__in=[
            CreativeRenderJob.Status.QUEUED,
            CreativeRenderJob.Status.PROCESSING,
        ],
    ).update(
        status=CreativeRenderJob.Status.CANCELED,
        progress=100,
        stage="canceled",
        message="Composition archived",
        finished_at=timezone.now(),
        heartbeat_at=timezone.now(),
        updated_at=timezone.now(),
    )

    return locked