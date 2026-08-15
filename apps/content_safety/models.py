# apps/content_safety/models.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.content_safety.enums import (
    SafetyContext,
    SafetyDecision,
    SafetyInputType,
    SafetyRiskLevel,
)


class ContentSafetyAnalysisCache(models.Model):
    """
    Cache one provider analysis by canonical input hash.
    """

    id = models.BigAutoField(
        primary_key=True
    )

    input_type = models.CharField(
        max_length=16,
        choices=SafetyInputType.choices,
        db_index=True,
    )

    input_hash = models.CharField(
        max_length=64,
        db_index=True,
    )

    provider = models.CharField(
        max_length=32,
        default="openai",
        db_index=True,
    )

    provider_model = models.CharField(
        max_length=80,
        db_index=True,
    )

    provider_response_id = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    flagged = models.BooleanField(
        default=False,
        db_index=True,
    )

    categories = models.JSONField(
        default=dict,
        blank=True,
    )

    category_scores = models.JSONField(
        default=dict,
        blank=True,
    )

    applied_input_types = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    last_accessed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    expires_at = models.DateTimeField(
        db_index=True
    )

    class Meta:
        verbose_name = "Content Safety Analysis Cache"
        verbose_name_plural = "Content Safety Analysis Caches"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "input_type",
                    "input_hash",
                    "provider",
                    "provider_model",
                ],
                name="uniq_content_safety_analysis",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "input_type",
                    "input_hash",
                    "provider",
                    "provider_model",
                ],
                name="safety_analysis_lookup_idx",
            ),
            models.Index(
                fields=[
                    "expires_at",
                ],
                name="safety_analysis_expiry_idx",
            ),
        ]

    def touch(self) -> None:
        self.last_accessed_at = timezone.now()

        self.save(
            update_fields=[
                "last_accessed_at",
            ]
        )

    def __str__(self) -> str:
        return (
            f"SafetyAnalysis<{self.input_type} "
            f"{self.input_hash[:12]} "
            f"{self.provider_model}>"
        )


class ContentSafetyAdjudicationCache(models.Model):
    """
    Cache one contextual adjudication result.
    """

    id = models.BigAutoField(
        primary_key=True
    )

    input_hash = models.CharField(
        max_length=64,
        db_index=True,
    )

    context = models.CharField(
        max_length=40,
        choices=SafetyContext.choices,
        db_index=True,
    )

    signal_hash = models.CharField(
        max_length=64,
        db_index=True,
    )

    policy_version = models.CharField(
        max_length=32,
        db_index=True,
    )

    model = models.CharField(
        max_length=80,
        db_index=True,
    )

    decision = models.CharField(
        max_length=16,
        choices=SafetyDecision.choices,
        db_index=True,
    )

    risk_level = models.CharField(
        max_length=16,
        choices=SafetyRiskLevel.choices,
        db_index=True,
    )

    reason_code = models.CharField(
        max_length=64,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    last_accessed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    expires_at = models.DateTimeField(
        db_index=True
    )

    class Meta:
        verbose_name = "Content Safety Adjudication Cache"
        verbose_name_plural = "Content Safety Adjudication Caches"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "input_hash",
                    "context",
                    "signal_hash",
                    "policy_version",
                    "model",
                ],
                name="uniq_safety_adjudication",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "input_hash",
                    "context",
                    "signal_hash",
                    "policy_version",
                    "model",
                ],
                name="safety_adj_lookup_idx",
            ),
            models.Index(
                fields=[
                    "expires_at",
                ],
                name="safety_adj_expiry_idx",
            ),
        ]

    def touch(self) -> None:
        self.last_accessed_at = timezone.now()

        self.save(
            update_fields=[
                "last_accessed_at",
            ]
        )

    def __str__(self) -> str:
        return (
            f"SafetyAdjudication<{self.context} "
            f"{self.decision} "
            f"{self.input_hash[:12]}>"
        )


class ContentSafetyEvent(models.Model):
    """
    Keep actionable moderation decisions for audit.
    """

    id = models.BigAutoField(
        primary_key=True
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="content_safety_events",
    )

    input_type = models.CharField(
        max_length=16,
        choices=SafetyInputType.choices,
        default=SafetyInputType.TEXT,
        db_index=True,
    )

    input_hash = models.CharField(
        max_length=64,
        db_index=True,
    )

    context = models.CharField(
        max_length=40,
        choices=SafetyContext.choices,
        default=SafetyContext.GENERIC,
        db_index=True,
    )

    field_name = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    decision = models.CharField(
        max_length=16,
        choices=SafetyDecision.choices,
        db_index=True,
    )

    risk_level = models.CharField(
        max_length=16,
        choices=SafetyRiskLevel.choices,
        db_index=True,
    )

    reason_code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    policy_version = models.CharField(
        max_length=32,
        db_index=True,
    )

    provider = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )

    provider_model = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    provider_flagged = models.BooleanField(
        default=False,
    )

    adjudicated = models.BooleanField(
        default=False,
        db_index=True,
    )

    adjudication_model = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        verbose_name = "Content Safety Event"
        verbose_name_plural = "Content Safety Events"

        indexes = [
            models.Index(
                fields=[
                    "decision",
                    "created_at",
                ],
                name="safety_event_decision_idx",
            ),
            models.Index(
                fields=[
                    "context",
                    "created_at",
                ],
                name="safety_event_context_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"SafetyEvent<{self.context} "
            f"{self.decision} "
            f"{self.reason_code}>"
        )