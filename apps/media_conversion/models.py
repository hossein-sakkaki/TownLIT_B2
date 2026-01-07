# apps/media_conversion/models.py
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class MediaJobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"
    CANCELED = "canceled", "Canceled"

class MediaConversionJob(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    field_name = models.CharField(max_length=64)   # video / audio / image / thumbnail...
    kind = models.CharField(max_length=16)         # video/audio/image
    status = models.CharField(max_length=16, choices=MediaJobStatus.choices, default=MediaJobStatus.QUEUED)

    task_id = models.CharField(max_length=64, null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)  # optional (0..100)
    message = models.CharField(max_length=255, null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    source_path = models.TextField(null=True, blank=True)
    output_path = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["task_id"]),
        ]
        unique_together = [("content_type", "object_id", "field_name")]
