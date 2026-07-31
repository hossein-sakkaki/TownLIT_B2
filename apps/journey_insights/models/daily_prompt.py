# apps/journey_insights/models/daily_prompt.py

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.journey_insights.constants import (
    DailyReflectionPromptStatus,
)


class DailyReflectionPrompt(models.Model):
    """
    One stable Reflection prompt for one user local day.
    """

    id = models.BigAutoField(
        primary_key=True,
    )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_reflection_prompts",
    )

    local_date = models.DateField(
        db_index=True,
    )

    timezone_name = models.CharField(
        max_length=64,
        default="UTC",
    )

    journey = models.ForeignKey(
        "posts.Journey",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="daily_reflection_prompts",
    )

    first_source_entry = models.ForeignKey(
        "posts.JourneyEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="started_daily_reflection_prompts",
    )

    latest_source_entry = models.ForeignKey(
        "posts.JourneyEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="latest_daily_reflection_prompts",
    )

    session = models.OneToOneField(
        "journey_insights.ReflectionSession",
        on_delete=models.CASCADE,
        related_name="daily_prompt",
    )

    session_question = models.OneToOneField(
        "journey_insights.ReflectionSessionQuestion",
        on_delete=models.CASCADE,
        related_name="daily_prompt",
    )

    status = models.CharField(
        max_length=24,
        choices=DailyReflectionPromptStatus.choices,
        default=DailyReflectionPromptStatus.PENDING,
        db_index=True,
    )

    # A prompt is created before its first actual presentation.
    prompt_count = models.PositiveIntegerField(
        default=0,
    )

    deferred_count = models.PositiveIntegerField(
        default=0,
    )

    # These values remain null until the prompt is actually presented.
    first_prompted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_prompted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    deferred_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    skipped_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    answered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expired_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def is_resolved(self) -> bool:
        return self.status in {
            DailyReflectionPromptStatus.SKIPPED,
            DailyReflectionPromptStatus.ANSWERED,
            DailyReflectionPromptStatus.EXPIRED,
        }

    @property
    def should_present(self) -> bool:
        return self.status in {
            DailyReflectionPromptStatus.PENDING,
            DailyReflectionPromptStatus.DEFERRED,
        }

    def __str__(self) -> str:
        return (
            f"Daily Reflection · {self.user_id} · "
            f"{self.local_date} · {self.status}"
        )

    class Meta:
        verbose_name = "Daily Reflection Prompt"
        verbose_name_plural = "Daily Reflection Prompts"

        ordering = (
            "-local_date",
            "-id",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "user",
                    "local_date",
                ),
                name="jri_unique_user_daily_prompt",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "user",
                    "-local_date",
                    "status",
                ),
                name="jri_prompt_user_day_status_idx",
            ),
            models.Index(
                fields=(
                    "status",
                    "-last_prompted_at",
                ),
                name="jri_prompt_status_time_idx",
            ),
        ]