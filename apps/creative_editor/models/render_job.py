# apps/creative_editor/models/render_job.py

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from .base import PublicIDTimestampedModel


class CreativeRenderJob(PublicIDTimestampedModel):
    """
    Render one immutable composition revision.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    composition = models.ForeignKey(
        "creative_editor.CreativeComposition",
        on_delete=models.CASCADE,
        related_name="render_jobs",
    )
    requested_revision = models.PositiveIntegerField(db_index=True)
    document_snapshot = models.JSONField(default=dict)
    document_sha256 = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    progress = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=40, blank=True, default="")
    message = models.CharField(max_length=255, blank=True, default="")
    error = models.TextField(blank=True, default="")
    task_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    queue = models.CharField(max_length=40, default="creative_render")
    output_path = models.TextField(blank=True, default="")
    thumbnail_path = models.TextField(blank=True, default="")
    attempt = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    def mark_started(
        self,
        message: str = "Rendering composition",
    ) -> None:
        now = timezone.now()

        self.status = self.Status.PROCESSING
        self.progress = max(1, self.progress)
        self.stage = "preparing"
        self.message = message
        self.error = ""
        self.started_at = self.started_at or now
        self.heartbeat_at = now

        self.save(
            update_fields=[
                "status",
                "progress",
                "stage",
                "message",
                "error",
                "started_at",
                "heartbeat_at",
                "updated_at",
            ]
        )

    def mark_progress(
        self,
        *,
        progress: int,
        stage: str,
        message: str = "",
    ) -> None:
        self.progress = min(99, max(1, int(progress)))
        self.stage = (stage or "")[:40]
        self.message = (message or "")[:255]
        self.heartbeat_at = timezone.now()

        self.save(
            update_fields=[
                "progress",
                "stage",
                "message",
                "heartbeat_at",
                "updated_at",
            ]
        )

    def mark_done(
        self,
        *,
        output_path: str,
        thumbnail_path: str,
    ) -> None:
        now = timezone.now()

        self.status = self.Status.DONE
        self.progress = 100
        self.stage = "completed"
        self.message = "Render completed"
        self.error = ""
        self.output_path = output_path
        self.thumbnail_path = thumbnail_path
        self.finished_at = now
        self.heartbeat_at = now

        if self.started_at:
            self.duration_ms = int(
                (now - self.started_at).total_seconds() * 1000
            )

        self.save(
            update_fields=[
                "status",
                "progress",
                "stage",
                "message",
                "error",
                "output_path",
                "thumbnail_path",
                "finished_at",
                "heartbeat_at",
                "duration_ms",
                "updated_at",
            ]
        )

    def mark_failed(self, error: str) -> None:
        now = timezone.now()

        self.status = self.Status.FAILED
        self.progress = 100
        self.stage = "failed"
        self.message = "Render failed"
        self.error = (error or "")[:20_000]
        self.finished_at = now
        self.heartbeat_at = now

        if self.started_at:
            self.duration_ms = int(
                (now - self.started_at).total_seconds() * 1000
            )

        self.save(
            update_fields=[
                "status",
                "progress",
                "stage",
                "message",
                "error",
                "finished_at",
                "heartbeat_at",
                "duration_ms",
                "updated_at",
            ]
        )

    def mark_canceled(
        self,
        message: str = "Render canceled",
    ) -> None:
        now = timezone.now()

        self.status = self.Status.CANCELED
        self.progress = 100
        self.stage = "canceled"
        self.message = message[:255]
        self.finished_at = now
        self.heartbeat_at = now

        if self.started_at:
            self.duration_ms = int(
                (now - self.started_at).total_seconds() * 1000
            )

        self.save(
            update_fields=[
                "status",
                "progress",
                "stage",
                "message",
                "finished_at",
                "heartbeat_at",
                "duration_ms",
                "updated_at",
            ]
        )

    @property
    def is_active(self) -> bool:
        return self.status in {
            self.Status.QUEUED,
            self.Status.PROCESSING,
        }

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            self.Status.DONE,
            self.Status.FAILED,
            self.Status.CANCELED,
        }

    def __str__(self) -> str:
        return (
            f"Render · {self.composition.public_id} · "
            f"r{self.requested_revision}"
        )

    class Meta:
        verbose_name = "Creative Render Job"
        verbose_name_plural = "Creative Render Jobs"
        ordering = ("-created_at", "-id")

        indexes = [
            models.Index(
                fields=("composition", "status", "-created_at"),
                name="creative_rjob_comp_idx",
            ),
            models.Index(
                fields=("status", "heartbeat_at"),
                name="creative_render_health_idx",
            ),
            models.Index(
                fields=("queue", "status"),
                name="creative_render_queue_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=("composition", "requested_revision"),
                name="creative_unique_render_revision",
            ),
            models.CheckConstraint(
                check=Q(requested_revision__gt=0),
                name="creative_render_revision_gt_zero",
            ),
            models.CheckConstraint(
                check=Q(progress__lte=100),
                name="creative_render_progress_lte_100",
            ),
            models.CheckConstraint(
                check=Q(max_attempts__gt=0),
                name="creative_render_max_attempts_gt_zero",
            ),
        ]