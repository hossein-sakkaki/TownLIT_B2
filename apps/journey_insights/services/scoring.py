# apps/journey_insights/services/scoring.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from apps.journey_insights.constants import (
    REFLECTION_SCORING_VERSION,
    SCORE_SCALE_MAX,
    SCORE_SCALE_MIN,
)


@dataclass(frozen=True)
class ReflectionScoreResult:
    raw_score: Decimal
    normalized_score: Decimal
    dimension_scores: dict
    scoring_snapshot: dict


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _normalize_score(raw_score: Decimal, theoretical_min: Decimal, theoretical_max: Decimal):
    if theoretical_max <= theoretical_min:
        return Decimal("50.000")

    ratio = (raw_score - theoretical_min) / (theoretical_max - theoretical_min)
    ratio = max(Decimal("0"), min(Decimal("1"), ratio))

    score = Decimal(str(SCORE_SCALE_MIN)) + (
        ratio * Decimal(str(SCORE_SCALE_MAX - SCORE_SCALE_MIN))
    )

    return score.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def score_reflection_choices(*, question, selected_choices) -> ReflectionScoreResult:
    if not selected_choices:
        raise ValueError("At least one answer choice is required.")

    raw_score = sum((_decimal(choice.base_score) for choice in selected_choices), Decimal("0"))

    dimension_totals: dict[str, Decimal] = {}

    for choice in selected_choices:
        for dimension, weight in (choice.dimension_weights or {}).items():
            dimension_totals[dimension] = (
                dimension_totals.get(dimension, Decimal("0"))
                + _decimal(weight)
            )

    all_active_choices = list(question.choices.filter(is_active=True))

    possible_scores = [_decimal(choice.base_score) for choice in all_active_choices]
    theoretical_min = min(possible_scores) if possible_scores else Decimal("0")
    theoretical_max = max(possible_scores) if possible_scores else Decimal("1")

    normalized_score = _normalize_score(
        raw_score,
        theoretical_min,
        theoretical_max,
    )

    dimension_scores = {
        dimension: float(value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
        for dimension, value in dimension_totals.items()
    }

    return ReflectionScoreResult(
        raw_score=raw_score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        normalized_score=normalized_score,
        dimension_scores=dimension_scores,
        scoring_snapshot={
            "version": REFLECTION_SCORING_VERSION,
            "question_code": question.code,
            "choice_codes": [choice.code for choice in selected_choices],
            "theoretical_min": float(theoretical_min),
            "theoretical_max": float(theoretical_max),
            "dimension_weights": {
                choice.code: choice.dimension_weights
                for choice in selected_choices
            },
        },
    )