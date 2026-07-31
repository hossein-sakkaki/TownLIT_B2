# apps/journey_insights/services/question_selection.py

from __future__ import annotations

import hashlib
import hmac
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q

from apps.journey_insights.constants import (
    QUESTION_SELECTION_VERSION,
    REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
    REFLECTION_MAX_QUESTIONS_PER_SESSION,
    ReflectionQuestionStatus,
)
from apps.journey_insights.models import (
    ReflectionQuestion,
    ReflectionQuestionExposure,
)


PRIORITY_NEVER_PRESENTED = 3
PRIORITY_NOT_IN_CURRENT_CYCLE = 2
PRIORITY_RECYCLED = 1

NEW_USER_MAX_JOURNEY_ENTRIES = 4
NEW_USER_MAX_ACTIVE_DAYS = 2

HIGH_SENSITIVITY_THRESHOLD = 4
MAX_HIGH_SENSITIVITY_PER_SESSION = 1
MAX_DEEP_THEME_PER_SESSION = 1

DEEP_REFLECTION_THEMES = {
    "painful_memory",
    "old_pain",
    "wounded_dream",
    "spiritual_wound",
    "trust_wound",
    "inner_wound",
    "wound_message",
    "wound_response",
    "vigilance",
    "protective_pattern",
    "growth_and_grief",
    "pain_and_purpose",
    "recovering_voice",
    "conviction_and_shame",
}

DEEP_TIME_CONTEXTS = {
    "healing",
    "past_reflection",
    "painful_spiritual_experience",
    "relational_healing",
    "loss_or_change",
    "life_story",
    "triggered_memory",
}


@dataclass(frozen=True)
class SelectedReflectionQuestion:
    question: ReflectionQuestion
    selection_score: Decimal
    selection_reason: dict


@dataclass(frozen=True)
class QuestionCandidate:
    question: ReflectionQuestion
    priority: int
    was_ever_presented: bool
    was_presented_in_current_cycle: bool


@dataclass
class SelectionState:
    dimension_usage: dict[str, int]
    high_sensitivity_count: int = 0
    deep_theme_count: int = 0


def _selection_seed(*, user_id: int, cycle: int, nonce: str) -> int:
    """
    Build a deterministic server-side random seed.
    """

    secret = str(settings.SECRET_KEY).encode("utf-8")
    payload = f"{user_id}:{cycle}:{nonce}:{QUESTION_SELECTION_VERSION}".encode("utf-8")
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    return int(digest[:16], 16)


def _is_new_user(
    *,
    minimum_journey_entries: int,
    active_days_in_month: int,
) -> bool:
    """
    Treat genuinely low Journey activity as a new Reflection user.

    Both lifetime Journey activity and current-month activity must remain
    within the new-user thresholds. This prevents established users with
    a temporarily quiet month from being classified as new users.
    """

    journey_entries = max(
        0,
        int(minimum_journey_entries),
    )
    active_days = max(
        0,
        int(active_days_in_month),
    )

    return (
        journey_entries <= NEW_USER_MAX_JOURNEY_ENTRIES
        and active_days <= NEW_USER_MAX_ACTIVE_DAYS
    )


def _question_theme(question: ReflectionQuestion) -> str:
    metadata = question.metadata or {}
    return str(metadata.get("theme") or "").strip().lower()


def _question_time_context(question: ReflectionQuestion) -> str:
    metadata = question.metadata or {}
    return str(metadata.get("time_context") or "").strip().lower()


def _is_deep_reflection_question(question: ReflectionQuestion) -> bool:
    """
    Detect questions involving wounds, grief, trauma-related patterns,
    spiritual injury, or other emotionally deep themes.
    """

    return (
        _question_theme(question) in DEEP_REFLECTION_THEMES
        or _question_time_context(question) in DEEP_TIME_CONTEXTS
    )


def _latest_exposure_cycle(
    *,
    exposure_map: dict[int, ReflectionQuestionExposure],
) -> int:
    if not exposure_map:
        return 1

    return max(
        int(exposure.exposure_cycle or 1)
        for exposure in exposure_map.values()
    )


def _build_candidate_groups(
    *,
    eligible: list[ReflectionQuestion],
    exposure_map: dict[int, ReflectionQuestionExposure],
    current_cycle: int,
) -> tuple[list[QuestionCandidate], list[QuestionCandidate]]:
    """
    Build remaining and recycled candidate pools.

    Never-presented questions always receive the highest priority.
    """

    remaining: list[QuestionCandidate] = []
    recycled: list[QuestionCandidate] = []

    for question in eligible:
        exposure = exposure_map.get(question.pk)

        if exposure is None:
            candidate = QuestionCandidate(
                question=question,
                priority=PRIORITY_NEVER_PRESENTED,
                was_ever_presented=False,
                was_presented_in_current_cycle=False,
            )
            remaining.append(candidate)
            recycled.append(candidate)
            continue

        exposure_cycle = int(exposure.exposure_cycle or 1)
        was_presented_in_current_cycle = exposure_cycle == current_cycle

        if not was_presented_in_current_cycle:
            remaining.append(
                QuestionCandidate(
                    question=question,
                    priority=PRIORITY_NOT_IN_CURRENT_CYCLE,
                    was_ever_presented=True,
                    was_presented_in_current_cycle=False,
                )
            )

        recycled.append(
            QuestionCandidate(
                question=question,
                priority=(
                    PRIORITY_RECYCLED
                    if was_presented_in_current_cycle
                    else PRIORITY_NOT_IN_CURRENT_CYCLE
                ),
                was_ever_presented=True,
                was_presented_in_current_cycle=was_presented_in_current_cycle,
            )
        )

    return remaining, recycled


def _resolve_selection_cycle(
    *,
    current_cycle: int,
    remaining_count: int,
    requested_count: int,
    has_any_exposure: bool,
) -> tuple[int, bool]:
    """
    Start a new cycle only when the current cycle cannot fill the session.
    """

    if remaining_count >= requested_count:
        return current_cycle, False

    if not has_any_exposure:
        return current_cycle, False

    return current_cycle + 1, True


def _candidate_allowed(
    *,
    candidate: QuestionCandidate,
    state: SelectionState,
) -> bool:
    question = candidate.question

    if (
        question.sensitivity >= HIGH_SENSITIVITY_THRESHOLD
        and state.high_sensitivity_count >= MAX_HIGH_SENSITIVITY_PER_SESSION
    ):
        return False

    if (
        _is_deep_reflection_question(question)
        and state.deep_theme_count >= MAX_DEEP_THEME_PER_SESSION
    ):
        return False

    return True


def _candidate_relaxation_level(
    *,
    candidate: QuestionCandidate,
    state: SelectionState,
) -> int:
    """
    Return how many safety limits would need relaxing.

    Lower values are preferred. This is used only when the strict pool
    cannot fill the requested session.
    """

    question = candidate.question
    violations = 0

    if (
        question.sensitivity >= HIGH_SENSITIVITY_THRESHOLD
        and state.high_sensitivity_count >= MAX_HIGH_SENSITIVITY_PER_SESSION
    ):
        violations += 1

    if (
        _is_deep_reflection_question(question)
        and state.deep_theme_count >= MAX_DEEP_THEME_PER_SESSION
    ):
        violations += 1

    return violations


def _question_score(
    *,
    candidate: QuestionCandidate,
    state: SelectionState,
    rng: random.Random,
    is_new_user: bool,
) -> Decimal:
    """
    Calculate the internal ordering score inside the same hard priority.
    """

    question = candidate.question

    dimension_penalty = (
        state.dimension_usage.get(question.primary_dimension, 0)
        * 0.45
    )

    brand_bonus = 0.18 if question.is_brand_core else 0.0
    fresh_bonus = 0.40 if not candidate.was_ever_presented else 0.0

    sensitivity_penalty = 0.0

    if is_new_user:
        sensitivity_penalty = max(
            float(question.sensitivity - 1) * 0.18,
            0.0,
        )
    elif question.sensitivity >= HIGH_SENSITIVITY_THRESHOLD:
        sensitivity_penalty = 0.08

    deep_theme_penalty = (
        0.16
        if _is_deep_reflection_question(question)
        else 0.0
    )

    difficulty = min(max(float(question.difficulty or 1), 1.0), 5.0)
    difficulty_balance = difficulty * 0.012

    random_component = rng.uniform(0.0, 0.35)

    score = (
        float(question.selection_weight)
        + brand_bonus
        + fresh_bonus
        + difficulty_balance
        + random_component
        - dimension_penalty
        - sensitivity_penalty
        - deep_theme_penalty
    )

    return Decimal(str(round(score, 6)))


def _mark_selected(
    *,
    question: ReflectionQuestion,
    state: SelectionState,
) -> None:
    state.dimension_usage[question.primary_dimension] = (
        state.dimension_usage.get(question.primary_dimension, 0) + 1
    )

    if question.sensitivity >= HIGH_SENSITIVITY_THRESHOLD:
        state.high_sensitivity_count += 1

    if _is_deep_reflection_question(question):
        state.deep_theme_count += 1


def _remove_candidate(
    *,
    candidate_pool: list[QuestionCandidate],
    question_id: int,
) -> list[QuestionCandidate]:
    return [
        candidate
        for candidate in candidate_pool
        if candidate.question.pk != question_id
    ]


def _highest_available_priority(
    candidates: Iterable[QuestionCandidate],
) -> int | None:
    priorities = [candidate.priority for candidate in candidates]
    return max(priorities) if priorities else None


def _choose_questions(
    *,
    candidate_pool: list[QuestionCandidate],
    requested_count: int,
    rng: random.Random,
    selection_cycle: int,
    rolled_over: bool,
    is_new_user: bool,
) -> list[SelectedReflectionQuestion]:
    """
    Select questions with hard repetition, sensitivity, and depth controls.
    """

    selected: list[SelectedReflectionQuestion] = []
    remaining_candidates = list(candidate_pool)
    state = SelectionState(dimension_usage={})

    while remaining_candidates and len(selected) < requested_count:
        allowed_candidates = [
            candidate
            for candidate in remaining_candidates
            if _candidate_allowed(candidate=candidate, state=state)
        ]

        relaxed_selection = False

        if not allowed_candidates:
            minimum_relaxation = min(
                _candidate_relaxation_level(
                    candidate=candidate,
                    state=state,
                )
                for candidate in remaining_candidates
            )

            allowed_candidates = [
                candidate
                for candidate in remaining_candidates
                if _candidate_relaxation_level(
                    candidate=candidate,
                    state=state,
                ) == minimum_relaxation
            ]
            relaxed_selection = True

        highest_priority = _highest_available_priority(allowed_candidates)

        priority_candidates = [
            candidate
            for candidate in allowed_candidates
            if candidate.priority == highest_priority
        ]

        scored_candidates = []

        for candidate in priority_candidates:
            score = _question_score(
                candidate=candidate,
                state=state,
                rng=rng,
                is_new_user=is_new_user,
            )

            scored_candidates.append(
                (
                    score,
                    rng.random(),
                    candidate,
                )
            )

        scored_candidates.sort(
            key=lambda row: (row[0], row[1]),
            reverse=True,
        )

        score, _, chosen_candidate = scored_candidates[0]
        chosen = chosen_candidate.question

        selected.append(
            SelectedReflectionQuestion(
                question=chosen,
                selection_score=score,
                selection_reason={
                    "cycle": selection_cycle,
                    "priority": chosen_candidate.priority,
                    "dimension": chosen.primary_dimension,
                    "sensitivity": chosen.sensitivity,
                    "deep_theme": _is_deep_reflection_question(chosen),
                    "previously_exposed": chosen_candidate.was_ever_presented,
                    "presented_in_current_cycle": (
                        chosen_candidate.was_presented_in_current_cycle
                    ),
                    "cycle_rollover": rolled_over,
                    "new_user_policy": is_new_user,
                    "selection_limits_relaxed": relaxed_selection,
                    "algorithm": QUESTION_SELECTION_VERSION,
                },
            )
        )

        _mark_selected(
            question=chosen,
            state=state,
        )

        remaining_candidates = _remove_candidate(
            candidate_pool=remaining_candidates,
            question_id=chosen.pk,
        )

    return selected


@transaction.atomic
def select_reflection_questions(
    *,
    user,
    count: int = REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
    nonce: str,
    minimum_journey_entries: int,
    active_days_in_month: int,
) -> tuple[int, list[SelectedReflectionQuestion]]:
    """
    Select a balanced non-repeating Reflection session.

    Guarantees:
    - Never-presented questions are prioritized.
    - New bank questions are considered immediately.
    - Questions are not repeated before the active cycle is exhausted.
    - New users do not receive questions marked as unsuitable for them.
    - A session normally contains no more than one high-sensitivity question.
    - A session normally contains no more than one deep-reflection question.
    - Primary dimensions are diversified where possible.
    """

    requested_count = max(
        1,
        min(int(count), REFLECTION_MAX_QUESTIONS_PER_SESSION),
    )

    user_is_new = _is_new_user(
        minimum_journey_entries=minimum_journey_entries,
        active_days_in_month=active_days_in_month,
    )

    activity_eligibility = Q(
        minimum_journey_entries__lte=minimum_journey_entries,
        minimum_active_days_in_month__lte=active_days_in_month,
    )

    if user_is_new:
        question_eligibility = (
            activity_eligibility
            | Q(allow_for_new_users=True)
        )
    else:
        question_eligibility = activity_eligibility

    question_filters = (
        Q(
            status=ReflectionQuestionStatus.ACTIVE,
            is_active=True,
        )
        & question_eligibility
    )

    eligible = list(
        ReflectionQuestion.objects
        .filter(question_filters)
        .annotate(
            active_choice_count=Count(
                "choices",
                filter=Q(choices__is_active=True),
                distinct=True,
            )
        )
        .filter(active_choice_count__gte=2)
        .prefetch_related("choices")
        .order_by("id")
    )

    if not eligible:
        return 1, []

    active_question_ids = [
        question.pk
        for question in eligible
    ]

    exposure_map = {
        exposure.question_id: exposure
        for exposure in (
            ReflectionQuestionExposure.objects
            .select_for_update()
            .filter(
                user=user,
                question_id__in=active_question_ids,
            )
        )
    }

    current_cycle = _latest_exposure_cycle(
        exposure_map=exposure_map,
    )

    remaining_candidates, recycled_candidates = _build_candidate_groups(
        eligible=eligible,
        exposure_map=exposure_map,
        current_cycle=current_cycle,
    )

    selection_cycle, rolled_over = _resolve_selection_cycle(
        current_cycle=current_cycle,
        remaining_count=len(remaining_candidates),
        requested_count=requested_count,
        has_any_exposure=bool(exposure_map),
    )

    candidate_pool = (
        recycled_candidates
        if rolled_over
        else remaining_candidates
    )

    if not candidate_pool:
        return selection_cycle, []

    rng = random.Random(
        _selection_seed(
            user_id=user.pk,
            cycle=selection_cycle,
            nonce=nonce,
        )
    )

    selected = _choose_questions(
        candidate_pool=candidate_pool,
        requested_count=min(requested_count, len(candidate_pool)),
        rng=rng,
        selection_cycle=selection_cycle,
        rolled_over=rolled_over,
        is_new_user=user_is_new,
    )

    return selection_cycle, selected