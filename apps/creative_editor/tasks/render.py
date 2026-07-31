# apps/creative_editor/tasks/render.py

from __future__ import annotations

import logging

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.creative_editor.constants import (
    CREATIVE_RENDER_MAX_RETRIES,
    CREATIVE_RENDER_QUEUE,
    CREATIVE_RENDER_RETRY_COUNTDOWN_SECONDS,
)
from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)
from apps.creative_editor.services.render_output import (
    CreativeRenderOutput,
    delete_render_output,
    persist_render_output,
)
from apps.creative_editor.services.renderer import (
    CreativeCompositionRenderer,
    CreativeRenderContext,
)


logger = logging.getLogger(__name__)


class StaleCreativeRender(Exception):
    """
    Raised when a newer composition revision exists.
    """


def _safe_delete_key(key: str) -> None:
    """
    Best-effort storage cleanup.
    """

    try:
        normalized = str(key or "").lstrip("/")

        if normalized and default_storage.exists(normalized):
            default_storage.delete(normalized)
    except Exception:
        logger.exception(
            "creative_editor.storage_cleanup.failed",
            extra={
                "storage_key": key,
            },
        )


def _replace_old_render_files(
    *,
    old_rendered_image: str,
    old_thumbnail: str,
    new_output: CreativeRenderOutput,
) -> None:
    """
    Remove previous canonical files after replacement.
    """

    for key in (
        old_rendered_image,
        old_thumbnail,
    ):
        normalized = str(key or "").lstrip("/")

        if normalized and normalized not in {
            new_output.output_path,
            new_output.thumbnail_path,
        }:
            _safe_delete_key(normalized)


@shared_task(
    bind=True,
    queue=CREATIVE_RENDER_QUEUE,
    autoretry_for=(),
    max_retries=CREATIVE_RENDER_MAX_RETRIES,
)
def render_creative_composition_task(
    self,
    *,
    render_job_id: int,
):
    """
    Render one immutable CreativeRenderJob snapshot.
    """

    close_old_connections()

    job = (
        CreativeRenderJob.objects.select_related(
            "composition",
            "composition__source_content_type",
        )
        .filter(pk=render_job_id)
        .first()
    )

    if job is None:
        logger.warning(
            "creative_editor.render_job.missing",
            extra={
                "render_job_id": render_job_id,
            },
        )
        return

    if job.status == CreativeRenderJob.Status.DONE:
        return

    if job.status == CreativeRenderJob.Status.CANCELED:
        return

    if (
        job.attempt >= job.max_attempts
        and job.status == CreativeRenderJob.Status.FAILED
    ):
        return

    output: CreativeRenderOutput | None = None

    try:
        job.attempt = min(
            job.max_attempts,
            int(job.attempt or 0) + 1,
        )
        job.task_id = str(self.request.id or "")

        job.save(
            update_fields=[
                "attempt",
                "task_id",
                "updated_at",
            ]
        )

        job.mark_started("Rendering composition")

        composition = job.composition

        if (
            not composition.is_active
            or composition.status == CreativeComposition.Status.ARCHIVED
        ):
            job.mark_canceled("Composition is archived")
            return

        renderer = CreativeCompositionRenderer()

        def progress(
            percent: int,
            stage: str,
            message: str,
        ) -> None:
            job.mark_progress(
                progress=percent,
                stage=stage,
                message=message,
            )

        rendered_image = renderer.render(
            context=CreativeRenderContext(
                composition=composition,
                document=job.document_snapshot,
                revision=job.requested_revision,
            ),
            progress_callback=progress,
        )

        job.mark_progress(
            progress=92,
            stage="encoding",
            message="Encoding render output",
        )

        output = persist_render_output(
            image=rendered_image,
            composition_id=composition.pk,
            revision=job.requested_revision,
        )

        job.mark_progress(
            progress=97,
            stage="publishing",
            message="Publishing render output",
        )

        with transaction.atomic():
            locked_composition = (
                CreativeComposition.objects.select_for_update()
                .get(pk=composition.pk)
            )

            locked_job = (
                CreativeRenderJob.objects.select_for_update()
                .get(pk=job.pk)
            )

            if locked_job.status == CreativeRenderJob.Status.CANCELED:
                raise StaleCreativeRender(
                    "Render job was canceled."
                )

            if locked_composition.revision != job.requested_revision:
                locked_job.mark_canceled(
                    "A newer composition revision exists"
                )

                raise StaleCreativeRender(
                    "A newer composition revision exists."
                )

            if locked_composition.document_sha256 != job.document_sha256:
                locked_job.mark_canceled(
                    "Composition document changed"
                )

                raise StaleCreativeRender(
                    "Composition document changed."
                )

            old_rendered_image = str(
                getattr(
                    locked_composition.rendered_image,
                    "name",
                    "",
                )
                or ""
            )

            old_thumbnail = str(
                getattr(
                    locked_composition.thumbnail,
                    "name",
                    "",
                )
                or ""
            )

            locked_composition.rendered_image = output.output_path
            locked_composition.thumbnail = output.thumbnail_path
            locked_composition.rendered_revision = job.requested_revision
            locked_composition.rendered_at = timezone.now()
            locked_composition.status = CreativeComposition.Status.READY
            locked_composition.render_error = ""

            media_assets = dict(
                locked_composition.media_assets or {}
            )

            media_assets["rendered_image"] = {
                "key": output.output_path,
                "mime_type": "image/jpeg",
                "width": output.width,
                "height": output.height,
                "revision": job.requested_revision,
            }

            media_assets["thumbnail"] = {
                "key": output.thumbnail_path,
                "mime_type": "image/jpeg",
                "revision": job.requested_revision,
            }

            locked_composition.media_assets = media_assets

            locked_composition.save(
                update_fields=[
                    "rendered_image",
                    "thumbnail",
                    "rendered_revision",
                    "rendered_at",
                    "status",
                    "render_error",
                    "media_assets",
                    "updated_at",
                ]
            )

            locked_job.mark_done(
                output_path=output.output_path,
                thumbnail_path=output.thumbnail_path,
            )

            transaction.on_commit(
                lambda: _replace_old_render_files(
                    old_rendered_image=old_rendered_image,
                    old_thumbnail=old_thumbnail,
                    new_output=output,
                )
            )

        logger.info(
            "creative_editor.render.completed",
            extra={
                "composition_id": composition.pk,
                "render_job_id": job.pk,
                "revision": job.requested_revision,
            },
        )

    except StaleCreativeRender:
        if output is not None:
            delete_render_output(output)

        logger.info(
            "creative_editor.render.stale",
            extra={
                "render_job_id": job.pk,
                "revision": job.requested_revision,
            },
        )

        return

    except Exception as exc:
        if output is not None:
            delete_render_output(output)

        logger.exception(
            "creative_editor.render.failed",
            extra={
                "render_job_id": job.pk,
                "composition_id": job.composition_id,
                "attempt": job.attempt,
            },
        )

        refreshed_job = (
            CreativeRenderJob.objects.filter(pk=job.pk)
            .first()
        )

        if refreshed_job is None:
            raise

        can_retry = (
            refreshed_job.attempt
            < refreshed_job.max_attempts
        )

        if can_retry:
            refreshed_job.status = CreativeRenderJob.Status.QUEUED
            refreshed_job.progress = 0
            refreshed_job.stage = "retry"
            refreshed_job.message = "Queued for retry"
            refreshed_job.error = str(exc)[:20_000]
            refreshed_job.heartbeat_at = timezone.now()

            refreshed_job.save(
                update_fields=[
                    "status",
                    "progress",
                    "stage",
                    "message",
                    "error",
                    "heartbeat_at",
                    "updated_at",
                ]
            )

            raise self.retry(
                exc=exc,
                countdown=CREATIVE_RENDER_RETRY_COUNTDOWN_SECONDS,
            )

        refreshed_job.mark_failed(str(exc))

        CreativeComposition.objects.filter(
            pk=refreshed_job.composition_id,
            revision=refreshed_job.requested_revision,
        ).update(
            status=CreativeComposition.Status.FAILED,
            render_error=str(exc)[:20_000],
            updated_at=timezone.now(),
        )

        raise