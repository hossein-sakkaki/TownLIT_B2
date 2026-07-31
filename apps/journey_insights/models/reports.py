# apps/journey_insights/models/reports.py

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.journey_insights.constants import (
    InsightTrend,
    MONTHLY_INSIGHT_VERSION,
    MonthlyInsightStatus,
    ReflectionDimension,
)


class MonthlyInsightReport(models.Model):
    """
    Immutable monthly report snapshot.
    """

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monthly_insight_reports",
    )

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()

    period_start = models.DateField()
    period_end = models.DateField()

    timezone_name = models.CharField(max_length=64, default="UTC")

    status = models.CharField(
        max_length=16,
        choices=MonthlyInsightStatus.choices,
        default=MonthlyInsightStatus.BUILDING,
        db_index=True,
    )

    version = models.CharField(
        max_length=100,
        default=MONTHLY_INSIGHT_VERSION,
    )

    is_sufficient = models.BooleanField(default=False, db_index=True)

    journey_days_count = models.PositiveIntegerField(default=0)
    journey_entries_count = models.PositiveIntegerField(default=0)
    reflection_sessions_count = models.PositiveIntegerField(default=0)
    reflection_answers_count = models.PositiveIntegerField(default=0)

    overall_score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
    )

    previous_overall_score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
    )

    overall_trend = models.CharField(
        max_length=16,
        choices=InsightTrend.choices,
        default=InsightTrend.INSUFFICIENT,
    )

    dimension_scores = models.JSONField(default=dict, blank=True)
    dimension_trends = models.JSONField(default=dict, blank=True)

    highlights = models.JSONField(default=list, blank=True)
    growth_areas = models.JSONField(default=list, blank=True)
    reflection_summary = models.JSONField(default=dict, blank=True)
    journey_summary = models.JSONField(default=dict, blank=True)

    source_snapshots = models.JSONField(default=dict, blank=True)
    algorithm_snapshot = models.JSONField(default=dict, blank=True)

    generated_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()

        if self.month < 1 or self.month > 12:
            raise ValidationError(
                {"month": "Month must be between 1 and 12."}
            )

        if self.period_end < self.period_start:
            raise ValidationError(
                {
                    "period_end": (
                        "Period end cannot be before period start."
                    ),
                }
            )

    def __str__(self):
        return f"{self.user_id} · {self.year}-{self.month:02d}"

    class Meta:
        verbose_name = "Monthly Insight Report"
        verbose_name_plural = "Monthly Insight Reports"
        ordering = ("-year", "-month", "-id")

        constraints = [
            models.UniqueConstraint(
                fields=("user", "year", "month"),
                name="mon_ins_unique_user_period",
            ),
            models.CheckConstraint(
                check=Q(month__gte=1) & Q(month__lte=12),
                name="mon_ins_month_range",
            ),
        ]

        indexes = [
            models.Index(
                fields=("user", "-year", "-month"),
                name="mon_ins_user_hist_idx",
            ),
            models.Index(
                fields=("status", "generated_at"),
                name="mon_ins_status_idx",
            ),
        ]


class MonthlyInsightDimension(models.Model):
    """
    Query-friendly dimension snapshot.
    """

    id = models.BigAutoField(primary_key=True)

    report = models.ForeignKey(
        MonthlyInsightReport,
        on_delete=models.CASCADE,
        related_name="dimensions",
    )

    dimension = models.CharField(
        max_length=32,
        choices=ReflectionDimension.choices,
    )

    score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
    )

    previous_score = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        null=True,
        blank=True,
    )

    trend = models.CharField(
        max_length=16,
        choices=InsightTrend.choices,
        default=InsightTrend.INSUFFICIENT,
    )

    confidence = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=0,
    )

    sample_count = models.PositiveIntegerField(default=0)

    explanation_key = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    explanation_params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Monthly Insight Dimension"
        verbose_name_plural = "Monthly Insight Dimensions"
        ordering = ("dimension",)

        constraints = [
            models.UniqueConstraint(
                fields=("report", "dimension"),
                name="monthly_insight_unique_report_dimension",
            ),
        ]