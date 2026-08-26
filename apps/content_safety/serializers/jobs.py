# apps/content_safety/serializers/jobs.py

from rest_framework import serializers

from apps.content_safety.models import (
    ContentSafetyJob,
)


class ContentSafetyJobSerializer(
    serializers.ModelSerializer
):
    can_retry = serializers.BooleanField(
        read_only=True
    )

    class Meta:
        model = ContentSafetyJob

        fields = [
            "public_id",
            "input_type",
            "field_name",
            "context",
            "status",
            "stage",
            "decision",
            "risk_level",
            "reason_code",
            "retryable",
            "can_retry",
            "progress",
            "message",
            "attempt",
            "max_attempts",
            "conversion_job_id",
            "created_at",
            "updated_at",
            "started_at",
            "finished_at",
        ]

        read_only_fields = fields