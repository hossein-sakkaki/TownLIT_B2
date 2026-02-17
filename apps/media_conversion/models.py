# apps/media_conversion/models.py

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class MediaJobKind(models.TextChoices):
    VIDEO = "video", "Video"
    AUDIO = "audio", "Audio"
    IMAGE = "image", "Image"


class MediaJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"
    CANCELED = "canceled", "Canceled"


class MediaConversionJob(models.Model):
    # ---- generic target ----
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # ---- what is being converted ----
    field_name = models.CharField(max_length=64)  # video/audio/image/thumbnail...
    kind = models.CharField(max_length=16, choices=MediaJobKind.choices)

    # ---- lifecycle ----
    status = models.CharField(
        max_length=16,
        choices=MediaJobStatus.choices,
        default=MediaJobStatus.QUEUED,
        db_index=True,
    )
    progress = models.PositiveSmallIntegerField(default=0)  # 0..100 (optional)
    message = models.CharField(max_length=255, null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    # ---- celery ----
    task_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    queue = models.CharField(max_length=32, null=True, blank=True)

    # ---- io paths ----
    source_path = models.TextField(null=True, blank=True)
    output_path = models.TextField(null=True, blank=True)

    # ---- retries / health ----
    attempt = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    heartbeat_at = models.DateTimeField(null=True, blank=True)  # “still alive” signal

    # ---- timestamps ----
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---- stage-based progress (existing) ----
    stage = models.CharField(max_length=32, null=True, blank=True)
    stage_index = models.PositiveSmallIntegerField(null=True, blank=True)
    stage_count = models.PositiveSmallIntegerField(null=True, blank=True)
    stage_weight = models.PositiveSmallIntegerField(null=True, blank=True)
    stage_progress = models.FloatField(null=True, blank=True)
    stage_started_at = models.DateTimeField(null=True, blank=True)

    # ---- weighted timeline (NEW: required for true weighted percent) ----
    stage_plan = models.JSONField(
        null=True,
        blank=True,
        help_text="Ordered stage plan: [{key,label?,weight}] used for weighted timeline",
    )

    stage_total_weight = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Sum of weights across stage_plan (cached)",
        db_index=True,
    )

    stage_completed_weight = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Sum of weights of completed stages before current stage",
    )

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status", "updated_at"]),
            models.Index(fields=["kind", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "field_name"],
                name="uniq_media_job_per_object_field",
            )
        ]

    def touch_heartbeat(self):
        self.heartbeat_at = timezone.now()
        self.save(update_fields=["heartbeat_at", "updated_at"])

    def mark_started(self, msg="Processing..."):
        now = timezone.now()
        self.status = MediaJobStatus.PROCESSING
        self.message = msg
        self.error = None
        self.started_at = self.started_at or now
        self.heartbeat_at = now
        self.progress = max(self.progress, 1)
        self.save(update_fields=["status", "message", "error", "started_at", "heartbeat_at", "progress", "updated_at"])

    def mark_done(self, output_path=None, msg="Ready"):
        now = timezone.now()
        self.status = MediaJobStatus.DONE
        self.message = msg
        self.error = None
        if output_path:
            self.output_path = output_path
        self.finished_at = now
        if self.started_at:
            self.duration_ms = int((now - self.started_at).total_seconds() * 1000)
        self.progress = 100
        self.heartbeat_at = now
        self.save(update_fields=["status", "message", "error", "output_path", "finished_at", "duration_ms", "progress", "heartbeat_at", "updated_at"])

    def mark_failed(self, err: str):
        now = timezone.now()
        self.status = MediaJobStatus.FAILED
        self.message = "Failed"
        self.error = (err or "")[:20000]
        self.finished_at = now
        if self.started_at:
            self.duration_ms = int((now - self.started_at).total_seconds() * 1000)
        self.heartbeat_at = now
        self.save(update_fields=["status", "message", "error", "finished_at", "duration_ms", "heartbeat_at", "updated_at"])
