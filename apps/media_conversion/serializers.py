# apps/media_conversion/serializers.py

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import serializers

from apps.media_conversion.models import (
    MediaConversionJob,
    MediaJobKind,
    MediaJobStatus,
)


class MediaConversionJobSerializer(
    serializers.ModelSerializer
):
    content_type_id = serializers.IntegerField(
        read_only=True
    )

    content_type_model = (
        serializers.SerializerMethodField()
    )

    is_stale = (
        serializers.SerializerMethodField()
    )

    can_retry = (
        serializers.SerializerMethodField()
    )

    eta_ms = (
        serializers.SerializerMethodField()
    )

    can_cancel = (
        serializers.SerializerMethodField()
    )

    action_hint = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = MediaConversionJob

        fields = [
            "id",

            # Target
            "content_type_id",
            "content_type_model",
            "object_id",

            # Kind
            "field_name",
            "kind",

            # Lifecycle
            "status",
            "progress",
            "message",
            "error",

            # Celery
            "task_id",
            "queue",

            # IO
            "source_path",
            "output_path",

            # Health / retry
            "attempt",
            "max_attempts",
            "heartbeat_at",
            "is_stale",
            "can_retry",

            # Timing
            "created_at",
            "started_at",
            "finished_at",
            "duration_ms",
            "eta_ms",
            "updated_at",

            # Stage metadata
            "stage",
            "stage_index",
            "stage_count",
            "stage_weight",
            "stage_progress",
            "stage_started_at",

            # Weighted timeline
            "stage_plan",
            "stage_total_weight",
            "stage_completed_weight",

            # Actions
            "can_cancel",
            "action_hint",
        ]

        read_only_fields = fields

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def get_content_type_model(
        self,
        obj,
    ) -> str:
        try:
            ct: ContentType = (
                obj.content_type
            )

            return (
                f"{ct.app_label}."
                f"{ct.model}"
            )

        except Exception:
            return ""

    def get_is_stale(
        self,
        obj,
    ) -> bool:
        if (
            obj.status
            != MediaJobStatus.PROCESSING
        ):
            return False

        if not obj.heartbeat_at:
            return True

        return (
            obj.heartbeat_at
            < timezone.now()
            - timedelta(
                minutes=2
            )
        )

    def get_can_retry(
        self,
        obj,
    ) -> bool:
        """
        Match the real retry action lifecycle.
        """

        if obj.status not in {
            MediaJobStatus.FAILED,
            MediaJobStatus.CANCELED,
        }:
            return False

        if (
            obj.max_attempts is not None
            and (
                obj.attempt
                or 0
            ) >= obj.max_attempts
        ):
            return False

        # Workflow retry does not require source_path.
        if obj.kind == MediaJobKind.WORKFLOW:
            return True

        # Normal media retry requires an original source.
        if not obj.source_path:
            return False

        if obj.status == MediaJobStatus.CANCELED:
            #  API cancellation historically deletes some
            #  legacy media jobs.

            #  A canceled snapshot must not advertise Retry
            #  when its backing DB row no longer exists.
            return (
                MediaConversionJob.objects
                .filter(
                    pk=obj.pk
                )
                .exists()
            )

        return True

    def get_eta_ms(
        self,
        obj,
    ) -> int | None:
        if (
            obj.status
            != MediaJobStatus.PROCESSING
            or not obj.started_at
            or not obj.progress
            or obj.progress <= 0
        ):
            return None

        elapsed_ms = int(
            (
                timezone.now()
                - obj.started_at
            ).total_seconds()
            * 1000
        )

        total_estimated_ms = int(
            elapsed_ms
            * (
                100
                / obj.progress
            )
        )

        return max(
            0,
            total_estimated_ms
            - elapsed_ms,
        )

    def get_can_cancel(
        self,
        obj,
    ) -> bool:
        return obj.status in {
            MediaJobStatus.QUEUED,
            MediaJobStatus.PROCESSING,
        }

    def get_action_hint(
        self,
        obj,
    ) -> str:
        if obj.status == MediaJobStatus.QUEUED:
            return "Waiting to start."

        if obj.status == MediaJobStatus.PROCESSING:
            if self.get_is_stale(
                obj
            ):
                return (
                    "Processing appears stalled."
                )

            return "Processing media."

        if obj.status == MediaJobStatus.DONE:
            return "Media is ready."

        if obj.status == MediaJobStatus.FAILED:
            if self.get_can_retry(
                obj
            ):
                return (
                    "Conversion failed. "
                    "Retry is available."
                )

            return "Conversion failed."

        if obj.status == MediaJobStatus.CANCELED:
            if self.get_can_retry(
                obj
            ):
                return (
                    "Conversion was canceled. "
                    "Retry is available."
                )

            return "Conversion was canceled."

        return ""