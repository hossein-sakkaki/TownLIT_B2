# apps/journey_insights/services/reflections.py

from __future__ import annotations

import hashlib
import hmac
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.journey_insights.constants import (
    REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
    REFLECTION_SESSION_EXPIRY_HOURS,
    DailyReflectionPromptStatus,
    ReflectionSessionStatus,
    ReflectionSourceKind,
)
from apps.journey_insights.models import (
    ReflectionAnswer,
    ReflectionChoice,
    ReflectionQuestionExposure,
    ReflectionSession,
    ReflectionSessionQuestion,
)
from apps.journey_insights.services.question_selection import (
    select_reflection_questions,
)
from apps.journey_insights.services.scoring import (
    score_reflection_choices,
)
from apps.posts.models.journey import JourneyEntry
from apps.profiles.models.member import Member



class NoEligibleReflectionQuestionsError(ValidationError):
    """
    Raised when no Reflection question can safely fill a new session.

    This distinct exception allows optional surfaces such as the Daily
    Reflection prompt to fail open without hiding unrelated validation errors.
    """

    def __init__(
        self,
        *,
        journey_entries: int,
        active_days_in_month: int,
    ) -> None:
        self.journey_entries = max(
            0,
            int(journey_entries),
        )
        self.active_days_in_month = max(
            0,
            int(active_days_in_month),
        )

        super().__init__(
            {
                "reflection": [
                    (
                        "No eligible reflection questions "
                        "are currently available."
                    )
                ],
                "journey_entries": [
                    str(self.journey_entries)
                ],
                "active_days_in_month": [
                    str(self.active_days_in_month)
                ],
            }
        )
        

def _member_user_field_name() -> str:
    """
    Resolve the OneToOne/ForeignKey field connecting Member to the user model.

    TownLIT historically used different field names in profile models.
    """

    candidate_names = ("user", "name")

    for field_name in candidate_names:
        try:
            field = Member._meta.get_field(field_name)
        except Exception:
            continue

        if getattr(field, "is_relation", False):
            return field_name

    raise RuntimeError(
        "Could not resolve the Member-to-user relation. "
        "Expected a relational field named 'user' or 'name'."
    )


def _member_for_user(*, user) -> Member | None:
    """
    Resolve the Member profile without relying on a reverse accessor.
    """

    user_field_name = _member_user_field_name()

    return (
        Member.objects
        .filter(**{f"{user_field_name}_id": user.pk})
        .first()
    )


def _journey_activity_for_user(*, user) -> dict:
    """
    Return Journey activity used for reflection eligibility.
    """

    member = _member_for_user(user=user)

    if member is None:
        return {
            "has_member_profile": False,
            "journey_entries": 0,
            "active_days_in_month": 0,
        }

    now = timezone.now()
    month_start = now.date().replace(day=1)

    member_content_type = ContentType.objects.get_for_model(
        Member,
        for_concrete_model=False,
    )

    entries = JourneyEntry.objects.filter(
        content_type=member_content_type,
        object_id=member.pk,
    )

    journey_entries = entries.count()

    active_days_in_month = (
        entries
        .filter(
            journey__local_date__gte=month_start,
            journey__local_date__lte=now.date(),
        )
        .values("journey__local_date")
        .distinct()
        .count()
    )

    return {
        "has_member_profile": True,
        "member_id": member.pk,
        "journey_entries": journey_entries,
        "active_days_in_month": active_days_in_month,
    }


def _choice_shuffle_seed(*, session_public_id, question_id: int) -> int:
    """
    Build a private deterministic seed for one session question.

    Refreshing the session keeps the same order, while different sessions
    receive different choice orders.
    """

    secret = str(settings.SECRET_KEY).encode("utf-8")
    payload = f"{session_public_id}:{question_id}:reflection-choices-v1".encode("utf-8")
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    return int(digest[:16], 16)


def _choice_snapshot(*, session: ReflectionSession, question) -> list[dict]:
    """
    Build and shuffle the public choice snapshot.

    Scoring metadata is intentionally excluded.
    """

    choices = list(
        question.choices
        .filter(is_active=True)
        .order_by("order", "id")
    )

    rng = random.Random(
        _choice_shuffle_seed(
            session_public_id=session.public_id,
            question_id=question.pk,
        )
    )
    rng.shuffle(choices)

    return [
        {
            "public_id": str(choice.public_id),
            "code": choice.code,
            "label": choice.label,
            "order": display_order,
        }
        for display_order, choice in enumerate(choices, start=1)
    ]


@transaction.atomic
def create_reflection_session(
    *,
    user,
    source_object=None,
    source_kind: str = ReflectionSourceKind.JOURNEY,
    question_count: int = REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
    reuse_existing_open: bool = True,
) -> ReflectionSession:
    """
    Create or return the current open Reflection session.
    """

    now = timezone.now()

    if reuse_existing_open:
        existing = (
            ReflectionSession.objects
            .select_for_update()
            .filter(
                user=user,
                status=ReflectionSessionStatus.OPEN,
                expires_at__gt=now,
            )
            .order_by("-opened_at", "-id")
            .first()
        )

        if existing is not None:
            return existing

    activity = _journey_activity_for_user(user=user)

    if not activity["has_member_profile"]:
        raise ValidationError(
            "An active Member profile is required to create a Journey reflection."
        )

    session = ReflectionSession.objects.create(
        user=user,
        source_kind=source_kind,
        source_content_type=(
            ContentType.objects.get_for_model(
                source_object,
                for_concrete_model=False,
            )
            if source_object is not None
            else None
        ),
        source_object_id=source_object.pk if source_object is not None else None,
        status=ReflectionSessionStatus.OPEN,
        opened_at=now,
        expires_at=now + timedelta(hours=REFLECTION_SESSION_EXPIRY_HOURS),
        selection_context={
            "member_id": activity["member_id"],
            "journey_entries": activity["journey_entries"],
            "active_days_in_month": activity["active_days_in_month"],
        },
    )

    cycle, selected_questions = select_reflection_questions(
        user=user,
        count=question_count,
        nonce=str(session.public_id),
        minimum_journey_entries=activity["journey_entries"],
        active_days_in_month=activity["active_days_in_month"],
    )

    if not selected_questions:
        raise NoEligibleReflectionQuestionsError(
            journey_entries=activity["journey_entries"],
            active_days_in_month=activity["active_days_in_month"],
        )

    assignments = []

    for position, selected in enumerate(selected_questions, start=1):
        question = selected.question

        assignments.append(
            ReflectionSessionQuestion(
                session=session,
                question=question,
                position=position,
                prompt_snapshot=question.prompt,
                kind_snapshot=question.kind,
                primary_dimension_snapshot=question.primary_dimension,
                choice_snapshot=_choice_snapshot(
                    session=session,
                    question=question,
                ),
                selection_score=selected.selection_score,
                selection_reason=selected.selection_reason,
            )
        )

    ReflectionSessionQuestion.objects.bulk_create(assignments)

    session.question_count = len(assignments)
    session.selection_context = {
        **session.selection_context,
        "exposure_cycle": cycle,
    }
    session.save(update_fields=[
        "question_count",
        "selection_context",
        "updated_at",
    ])

    exposure_now = timezone.now()

    persisted_assignments = (
        ReflectionSessionQuestion.objects
        .select_related("question")
        .filter(session=session)
        .order_by("position", "id")
    )

    for assignment in persisted_assignments:
        exposure, created = (
            ReflectionQuestionExposure.objects
            .select_for_update()
            .get_or_create(
                user=user,
                question=assignment.question,
                defaults={
                    "exposure_cycle": cycle,
                    "times_presented": 1,
                    "first_presented_at": exposure_now,
                    "last_presented_at": exposure_now,
                },
            )
        )

        if created:
            continue

        exposure.exposure_cycle = cycle
        exposure.times_presented = F("times_presented") + 1
        exposure.last_presented_at = exposure_now
        exposure.save(update_fields=[
            "exposure_cycle",
            "times_presented",
            "last_presented_at",
            "updated_at",
        ])

    return session


@transaction.atomic
def submit_reflection_answer(
    *,
    user,
    session_question: ReflectionSessionQuestion,
    selected_choice_public_ids: list,
) -> ReflectionAnswer:
    """
    Validate, score, and persist one Reflection answer.
    """

    assignment = (
        ReflectionSessionQuestion.objects
        .select_for_update()
        .select_related("session", "question")
        .get(pk=session_question.pk)
    )

    session = assignment.session

    if session.user_id != user.pk:
        raise ValidationError("This reflection session does not belong to you.")

    if session.status != ReflectionSessionStatus.OPEN:
        raise ValidationError("This reflection session is not open.")

    if session.expires_at <= timezone.now():
        session.status = ReflectionSessionStatus.EXPIRED
        session.save(update_fields=["status", "updated_at"])
        raise ValidationError("This reflection session has expired.")

    if ReflectionAnswer.objects.filter(session_question=assignment).exists():
        raise ValidationError("This reflection question has already been answered.")

    choice_ids = {str(value) for value in selected_choice_public_ids}

    if not choice_ids:
        raise ValidationError("At least one answer choice is required.")

    choices = list(
        ReflectionChoice.objects.filter(
            question=assignment.question,
            public_id__in=choice_ids,
            is_active=True,
        )
    )

    if len(choices) != len(choice_ids):
        raise ValidationError("One or more selected choices are invalid.")

    if assignment.kind_snapshot == "single_choice" and len(choices) != 1:
        raise ValidationError("Exactly one answer must be selected.")

    score = score_reflection_choices(
        question=assignment.question,
        selected_choices=choices,
    )

    answer = ReflectionAnswer.objects.create(
        session_question=assignment,
        user=user,
        selected_choice_codes=[choice.code for choice in choices],
        response_value={
            "selected_choice_public_ids": [
                str(choice.public_id)
                for choice in choices
            ],
        },
        raw_score=score.raw_score,
        normalized_score=score.normalized_score,
        dimension_scores=score.dimension_scores,
        scoring_snapshot=score.scoring_snapshot,
    )

    answer.selected_choices.set(choices)

    answered_at = timezone.now()

    assignment.answered_at = answered_at
    assignment.save(update_fields=["answered_at"])

    ReflectionQuestionExposure.objects.filter(
        user=user,
        question=assignment.question,
    ).update(
        times_answered=F("times_answered") + 1,
        last_answered_at=answered_at,
        updated_at=answered_at,
    )

    answers = list(
        ReflectionAnswer.objects
        .filter(session_question__session=session)
        .order_by("submitted_at", "id")
    )

    answered_count = len(answers)
    session.answered_count = answered_count

    if answered_count >= session.question_count:
        total_score = sum(
            (item.normalized_score for item in answers),
            Decimal("0"),
        )

        dimension_totals: dict[str, list[float]] = {}

        for item in answers:
            for dimension, value in (item.dimension_scores or {}).items():
                dimension_totals.setdefault(dimension, []).append(float(value))

        session.score_total = (
            total_score / Decimal(str(max(answered_count, 1)))
        )

        session.dimension_scores = {
            dimension: round(sum(values) / len(values), 3)
            for dimension, values in dimension_totals.items()
            if values
        }

        session.status = ReflectionSessionStatus.COMPLETED
        session.completed_at = answered_at

        if hasattr(session, "daily_prompt"):
            daily_prompt = session.daily_prompt

            daily_prompt.status = (
                DailyReflectionPromptStatus.ANSWERED
            )
            daily_prompt.answered_at = answered_at

            daily_prompt.save(
                update_fields=[
                    "status",
                    "answered_at",
                    "updated_at",
                ]
            )
            
    session.save(update_fields=[
        "answered_count",
        "score_total",
        "dimension_scores",
        "status",
        "completed_at",
        "updated_at",
    ])

    return answer