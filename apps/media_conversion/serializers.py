# apps/media_conversion/serializers.py
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta

from apps.media_conversion.models import MediaConversionJob, MediaJobStatus


class MediaConversionJobSerializer(serializers.ModelSerializer):
    # Explicit for frontend
    content_type_id = serializers.IntegerField(read_only=True)
    content_type_model = serializers.SerializerMethodField()

    # Derived (lightweight)
    is_stale = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()
    eta_ms = serializers.SerializerMethodField()

    class Meta:
        model = MediaConversionJob
        fields = [
            "id",

            # target
            "content_type_id",
            "content_type_model",
            "object_id",

            # what
            "field_name",
            "kind",

            # lifecycle
            "status",
            "progress",
            "message",
            "error",

            # celery
            "task_id",
            "queue",

            # io
            "source_path",
            "output_path",

            # health/retry
            "attempt",
            "max_attempts",
            "heartbeat_at",
            "is_stale",
            "can_retry",

            # timing
            "created_at",
            "started_at",
            "finished_at",
            "duration_ms",
            "eta_ms",
            "updated_at",

            # ---- stage metadata ----
            "stage",
            "stage_index",
            "stage_count",
            "stage_weight",
            "stage_progress",
            "stage_started_at",

            # ---- weighted timeline (NEW) ----
            "stage_plan",
            "stage_total_weight",
            "stage_completed_weight",
        ]
        read_only_fields = fields

    # ---------------- helpers ----------------

    def get_content_type_model(self, obj) -> str:
        try:
            ct: ContentType = obj.content_type
            return f"{ct.app_label}.{ct.model}"
        except Exception:
            return ""

    def get_is_stale(self, obj) -> bool:
        """
        Indicates job is processing but heartbeat stopped.
        """
        if obj.status != MediaJobStatus.PROCESSING:
            return False
        if not obj.heartbeat_at:
            return True

        now = timezone.now()
        return obj.heartbeat_at < now - timedelta(minutes=2)

    def get_can_retry(self, obj) -> bool:
        """
        Frontend-safe retry decision.
        """
        if obj.status not in {MediaJobStatus.FAILED, MediaJobStatus.CANCELED}:
            return False
        if obj.max_attempts is None:
            return True
        return (obj.attempt or 0) < obj.max_attempts

    def get_eta_ms(self, obj) -> int | None:
        """
        Simple linear ETA estimate.
        Returns remaining milliseconds or None.
        """
        if (
            obj.status != MediaJobStatus.PROCESSING
            or not obj.started_at
            or not obj.progress
            or obj.progress <= 0
        ):
            return None

        elapsed_ms = int(
            (timezone.now() - obj.started_at).total_seconds() * 1000
        )

        # linear estimate
        total_estimated_ms = int(elapsed_ms * (100 / obj.progress))
        remaining_ms = max(0, total_estimated_ms - elapsed_ms)

        return remaining_ms
