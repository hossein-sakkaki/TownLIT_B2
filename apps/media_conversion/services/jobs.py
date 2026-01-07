# apps/media_conversion/services/jobs.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from apps.media_conversion.models import MediaConversionJob, MediaJobStatus

def upsert_job(instance, field_name, kind, *, status=None, task_id=None, source_path=None, message=None):
    ct = ContentType.objects.get_for_model(instance.__class__)
    job, _ = MediaConversionJob.objects.update_or_create(
        content_type=ct,
        object_id=instance.pk,
        field_name=field_name,
        defaults={
            "kind": kind,
            "status": status or MediaJobStatus.QUEUED,
            "task_id": task_id,
            "source_path": source_path,
            "message": message,
            "error": None,
            "progress": 0,
            "started_at": timezone.now() if (status == MediaJobStatus.PROCESSING) else None,
            "finished_at": timezone.now() if (status in (MediaJobStatus.DONE, MediaJobStatus.FAILED, MediaJobStatus.CANCELED)) else None,
        },
    )
    return job

def mark_processing(job: MediaConversionJob, message="Processing..."):
    job.status = MediaJobStatus.PROCESSING
    job.message = message
    job.started_at = job.started_at or timezone.now()
    job.progress = max(job.progress, 1)
    job.save(update_fields=["status", "message", "started_at", "progress", "updated_at"])

def mark_done(job: MediaConversionJob, output_path=None, message="Ready"):
    job.status = MediaJobStatus.DONE
    job.message = message
    job.output_path = output_path or job.output_path
    job.progress = 100
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "message", "output_path", "progress", "finished_at", "updated_at"])

def mark_failed(job: MediaConversionJob, error: str):
    job.status = MediaJobStatus.FAILED
    job.error = error
    job.message = "Failed"
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error", "message", "finished_at", "updated_at"])
