# apps/journey_insights/services/monthly_reports.py

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.journey_insights.constants import (
    InsightTrend,
    MONTHLY_INSIGHT_MIN_ACTIVE_DAYS,
    MONTHLY_INSIGHT_MIN_ANSWER_COUNT,
    MONTHLY_INSIGHT_VERSION,
    MonthlyInsightStatus,
)
from apps.journey_insights.models import (
    MonthlyInsightDimension,
    MonthlyInsightReport,
    ReflectionAnswer,
    ReflectionSession,
)
from apps.posts.models.journey import Journey, JourneyEntry


def _period(year: int, month: int):
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _previous_period(year: int, month: int):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _trend(current, previous):
    if current is None or previous is None:
        return InsightTrend.INSUFFICIENT

    delta = Decimal(str(current)) - Decimal(str(previous))

    if delta >= Decimal("3"):
        return InsightTrend.UP

    if delta <= Decimal("-3"):
        return InsightTrend.DOWN

    return InsightTrend.STABLE


def _normalize_dimension_value(value):
    numeric = Decimal(str(value))
    normalized = Decimal("50") + (numeric * Decimal("10"))
    normalized = max(Decimal("0"), min(Decimal("100"), normalized))
    return normalized.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def generate_monthly_insight_report(*, user, year: int, month: int):
    period_start, period_end = _period(year, month)

    report, _ = MonthlyInsightReport.objects.select_for_update().get_or_create(
        user=user,
        year=year,
        month=month,
        defaults={
            "period_start": period_start,
            "period_end": period_end,
            "status": MonthlyInsightStatus.BUILDING,
            "version": MONTHLY_INSIGHT_VERSION,
        },
    )

    report.status = MonthlyInsightStatus.BUILDING
    report.failure_reason = ""
    report.failed_at = None
    report.save(update_fields=[
        "status",
        "failure_reason",
        "failed_at",
        "updated_at",
    ])

    try:
        member = getattr(user, "member_profile", None)

        journey_days_count = 0
        journey_entries_count = 0

        if member is not None:
            member_ct = ContentType.objects.get_for_model(
                member.__class__,
                for_concrete_model=False,
            )

            journey_days_count = Journey.objects.filter(
                content_type=member_ct,
                object_id=member.pk,
                local_date__gte=period_start,
                local_date__lte=period_end,
                entries__isnull=False,
            ).distinct().count()

            journey_entries_count = JourneyEntry.objects.filter(
                content_type=member_ct,
                object_id=member.pk,
                published_at__date__gte=period_start,
                published_at__date__lte=period_end,
            ).count()

        sessions = ReflectionSession.objects.filter(
            user=user,
            completed_at__date__gte=period_start,
            completed_at__date__lte=period_end,
            status="completed",
        )

        answers = ReflectionAnswer.objects.filter(
            user=user,
            submitted_at__date__gte=period_start,
            submitted_at__date__lte=period_end,
            status="submitted",
        )

        answer_rows = list(
            answers.values(
                "normalized_score",
                "dimension_scores",
            )
        )

        overall_score = None

        if answer_rows:
            total = sum(
                (row["normalized_score"] for row in answer_rows),
                Decimal("0"),
            )
            overall_score = (
                total / Decimal(str(len(answer_rows)))
            ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

        dimension_values = defaultdict(list)

        for row in answer_rows:
            for dimension, value in (row["dimension_scores"] or {}).items():
                dimension_values[dimension].append(
                    _normalize_dimension_value(value)
                )

        dimension_scores = {
            dimension: float(
                (
                    sum(values, Decimal("0"))
                    / Decimal(str(len(values)))
                ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            )
            for dimension, values in dimension_values.items()
            if values
        }

        previous_year, previous_month = _previous_period(year, month)

        previous_report = MonthlyInsightReport.objects.filter(
            user=user,
            year=previous_year,
            month=previous_month,
            status=MonthlyInsightStatus.READY,
        ).first()

        previous_overall_score = (
            previous_report.overall_score
            if previous_report
            else None
        )

        previous_dimensions = (
            previous_report.dimension_scores
            if previous_report
            else {}
        )

        dimension_trends = {
            dimension: _trend(
                current,
                previous_dimensions.get(dimension),
            )
            for dimension, current in dimension_scores.items()
        }

        ranked_dimensions = sorted(
            dimension_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        highlights = [
            {
                "dimension": dimension,
                "score": score,
                "message_key": "journey_insight.highlight.dimension",
            }
            for dimension, score in ranked_dimensions[:3]
        ]

        growth_areas = [
            {
                "dimension": dimension,
                "score": score,
                "message_key": "journey_insight.growth.dimension",
            }
            for dimension, score in sorted(
                dimension_scores.items(),
                key=lambda item: item[1],
            )[:3]
        ]

        is_sufficient = (
            len(answer_rows) >= MONTHLY_INSIGHT_MIN_ANSWER_COUNT
            and journey_days_count >= MONTHLY_INSIGHT_MIN_ACTIVE_DAYS
        )

        report.period_start = period_start
        report.period_end = period_end
        report.status = MonthlyInsightStatus.READY
        report.version = MONTHLY_INSIGHT_VERSION
        report.is_sufficient = is_sufficient

        report.journey_days_count = journey_days_count
        report.journey_entries_count = journey_entries_count
        report.reflection_sessions_count = sessions.count()
        report.reflection_answers_count = len(answer_rows)

        report.overall_score = overall_score
        report.previous_overall_score = previous_overall_score
        report.overall_trend = _trend(overall_score, previous_overall_score)

        report.dimension_scores = dimension_scores
        report.dimension_trends = dimension_trends
        report.highlights = highlights if is_sufficient else []
        report.growth_areas = growth_areas if is_sufficient else []

        report.reflection_summary = {
            "completed_sessions": sessions.count(),
            "answers": len(answer_rows),
        }

        report.journey_summary = {
            "active_days": journey_days_count,
            "entries": journey_entries_count,
        }

        report.source_snapshots = {
            "journey": {
                "active_days": journey_days_count,
                "entries": journey_entries_count,
            },
            "reflection": {
                "sessions": sessions.count(),
                "answers": len(answer_rows),
            },
        }

        report.algorithm_snapshot = {
            "version": MONTHLY_INSIGHT_VERSION,
            "minimum_answers": MONTHLY_INSIGHT_MIN_ANSWER_COUNT,
            "minimum_active_days": MONTHLY_INSIGHT_MIN_ACTIVE_DAYS,
        }

        report.generated_at = timezone.now()

        report.save()

        report.dimensions.all().delete()

        dimension_rows = []

        for dimension, score in dimension_scores.items():
            previous_score = previous_dimensions.get(dimension)
            sample_count = len(dimension_values.get(dimension, []))

            confidence = min(
                Decimal("1"),
                Decimal(str(sample_count)) / Decimal("10"),
            )

            dimension_rows.append(
                MonthlyInsightDimension(
                    report=report,
                    dimension=dimension,
                    score=score,
                    previous_score=previous_score,
                    trend=dimension_trends.get(
                        dimension,
                        InsightTrend.INSUFFICIENT,
                    ),
                    confidence=confidence,
                    sample_count=sample_count,
                    explanation_key="journey_insight.dimension.summary",
                    explanation_params={
                        "dimension": dimension,
                        "score": score,
                    },
                )
            )

        MonthlyInsightDimension.objects.bulk_create(dimension_rows)

        return report

    except Exception as exc:
        report.status = MonthlyInsightStatus.FAILED
        report.failed_at = timezone.now()
        report.failure_reason = str(exc)[:2000]
        report.save(update_fields=[
            "status",
            "failed_at",
            "failure_reason",
            "updated_at",
        ])
        raise