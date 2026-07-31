# apps/journey_insights/services/daily_prompt.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from apps.journey_insights.constants import (
    DailyReflectionPromptDecision,
    DailyReflectionPromptStatus,
    ReflectionSessionStatus,
    ReflectionSourceKind,
)
from apps.journey_insights.models import (
    DailyReflectionPrompt,
    ReflectionSession,
)
from apps.journey_insights.services.daily_prompt_localization import (
    localize_daily_reflection_content,
)
from apps.journey_insights.services.reflections import (
    NoEligibleReflectionQuestionsError,
    create_reflection_session,
)
from apps.posts.models.journey import (
    Journey,
    JourneyEntry,
)
from apps.translations.services.language import (
    DEFAULT_SOURCE_LANGUAGE,
)
import logging
logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class DailyReflectionPromptResult:
    should_present: bool
    reason: str

    prompt_public_id: UUID | None

    local_date: object | None
    timezone_name: str | None
    status: str | None

    session_public_id: UUID | None
    session_question_public_id: UUID | None

    question_public_id: UUID | None
    question_code: str | None

    prompt: str | None
    kind: str | None
    choices: list[dict]

    prompt_count: int
    deferred_count: int

    source_language: str
    display_language: str
    is_translated: bool
    translation_cached: bool

    def as_dict(self) -> dict:
        return {
            "should_present": self.should_present,
            "reason": self.reason,
            "prompt_public_id": self.prompt_public_id,
            "local_date": self.local_date,
            "timezone_name": self.timezone_name,
            "status": self.status,
            "session_public_id": self.session_public_id,
            "session_question_public_id": (
                self.session_question_public_id
            ),
            "question_public_id": self.question_public_id,
            "question_code": self.question_code,
            "prompt": self.prompt,
            "kind": self.kind,
            "choices": self.choices,
            "prompt_count": self.prompt_count,
            "deferred_count": self.deferred_count,
            "source_language": self.source_language,
            "display_language": self.display_language,
            "is_translated": self.is_translated,
            "translation_cached": self.translation_cached,
        }


def _empty_result(
    *,
    reason: str,
    local_date: date | None = None,
    timezone_name: str | None = None,
) -> DailyReflectionPromptResult:
    return DailyReflectionPromptResult(
        should_present=False,
        reason=reason,
        prompt_public_id=None,
        local_date=local_date,
        timezone_name=timezone_name,
        status=None,
        session_public_id=None,
        session_question_public_id=None,
        question_public_id=None,
        question_code=None,
        prompt=None,
        kind=None,
        choices=[],
        prompt_count=0,
        deferred_count=0,
        source_language=DEFAULT_SOURCE_LANGUAGE,
        display_language=DEFAULT_SOURCE_LANGUAGE,
        is_translated=False,
        translation_cached=True,
    )


def _result_from_prompt(
    *,
    user,
    daily_prompt: DailyReflectionPrompt,
    should_present: bool,
    reason: str,
) -> DailyReflectionPromptResult:
    assignment = (
        daily_prompt.session_question
    )
    question = assignment.question

    localized = (
        localize_daily_reflection_content(
            user=user,
            question=question,
            prompt_snapshot=(
                assignment.prompt_snapshot
            ),
            choice_snapshot=(
                assignment.choice_snapshot
            ),
        )
    )

    return DailyReflectionPromptResult(
        should_present=should_present,
        reason=reason,
        prompt_public_id=daily_prompt.public_id,
        local_date=daily_prompt.local_date,
        timezone_name=daily_prompt.timezone_name,
        status=daily_prompt.status,
        session_public_id=(
            daily_prompt.session.public_id
        ),
        session_question_public_id=(
            assignment.public_id
        ),
        question_public_id=question.public_id,
        question_code=question.code,
        prompt=localized.prompt,
        kind=assignment.kind_snapshot,
        choices=localized.choices,
        prompt_count=daily_prompt.prompt_count,
        deferred_count=daily_prompt.deferred_count,
        source_language=(
            localized.source_language
        ),
        display_language=(
            localized.display_language
        ),
        is_translated=localized.is_translated,
        translation_cached=localized.all_cached,
    )


def _normalized_timezone_name(
    timezone_name: str | None,
) -> str:
    cleaned = str(
        timezone_name or ""
    ).strip()

    if not cleaned:
        return "UTC"

    try:
        ZoneInfo(
            cleaned
        )
    except ZoneInfoNotFoundError:
        return "UTC"

    return cleaned


def _local_date_for_timezone(
    timezone_name: str,
) -> date:
    zone = ZoneInfo(
        timezone_name
    )

    return timezone.now().astimezone(
        zone
    ).date()


def _expire_previous_prompts(
    *,
    user,
    current_local_date: date,
) -> None:
    """
    Expire unresolved prompts from earlier local days.
    """

    now = timezone.now()

    previous_prompts = (
        DailyReflectionPrompt.objects
        .select_for_update()
        .filter(
            user=user,
            local_date__lt=current_local_date,
            status__in=[
                DailyReflectionPromptStatus.PENDING,
                DailyReflectionPromptStatus.DEFERRED,
            ],
        )
    )

    session_ids = list(
        previous_prompts.values_list(
            "session_id",
            flat=True,
        )
    )

    previous_prompts.update(
        status=DailyReflectionPromptStatus.EXPIRED,
        expired_at=now,
        updated_at=now,
    )

    if session_ids:
        ReflectionSession.objects.filter(
            id__in=session_ids,
            status=ReflectionSessionStatus.OPEN,
        ).update(
            status=ReflectionSessionStatus.EXPIRED,
            updated_at=now,
        )


def _locked_prompt_for_day(
    *,
    user,
    local_date: date,
) -> DailyReflectionPrompt | None:
    return (
        DailyReflectionPrompt.objects
        .select_for_update()
        .select_related(
            "journey",
            "session",
            "session_question",
            "session_question__question",
        )
        .filter(
            user=user,
            local_date=local_date,
        )
        .first()
    )


def _resolved_existing_prompt(
    *,
    user,
    daily_prompt: DailyReflectionPrompt,
    represent_deferred: bool,
) -> DailyReflectionPromptResult:
    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.ANSWERED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="already_answered_today",
        )

    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.SKIPPED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="skipped_for_today",
        )

    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.EXPIRED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="daily_prompt_expired",
        )

    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.DEFERRED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=represent_deferred,
            reason=(
                "deferred_prompt_represented"
                if represent_deferred
                else "deferred_until_next_journey"
            ),
        )

    return _result_from_prompt(
        user=user,
        daily_prompt=daily_prompt,
        should_present=True,
        reason="pending_daily_prompt",
    )


def _create_prompt_for_day(
    *,
    user,
    local_date: date,
    timezone_name: str,
) -> DailyReflectionPrompt:
    """
    Create today's stable question before its first presentation.
    """

    session = create_reflection_session(
        user=user,
        source_object=None,
        source_kind=ReflectionSourceKind.JOURNEY,
        question_count=1,
        reuse_existing_open=False,
    )

    assignment = (
        session.session_questions
        .select_related(
            "question"
        )
        .order_by(
            "position",
            "id",
        )
        .first()
    )

    if assignment is None:
        raise RuntimeError(
            "Daily Reflection session was created without a question."
        )

    daily_prompt = (
        DailyReflectionPrompt.objects.create(
            user=user,
            local_date=local_date,
            timezone_name=timezone_name,
            journey=None,
            first_source_entry=None,
            latest_source_entry=None,
            session=session,
            session_question=assignment,
            status=DailyReflectionPromptStatus.PENDING,
            prompt_count=0,
            deferred_count=0,
            first_prompted_at=None,
            last_prompted_at=None,
        )
    )

    return (
        DailyReflectionPrompt.objects
        .select_related(
            "journey",
            "session",
            "session_question",
            "session_question__question",
        )
        .get(
            pk=daily_prompt.pk
        )
    )

def _mark_prompt_presented(
    *,
    daily_prompt: DailyReflectionPrompt,
) -> DailyReflectionPrompt:
    """
    Record one actual prompt presentation.
    """

    now = timezone.now()

    update_values = {
        "prompt_count": F("prompt_count") + 1,
        "last_prompted_at": now,
        "updated_at": now,
    }

    if daily_prompt.first_prompted_at is None:
        update_values["first_prompted_at"] = now

    DailyReflectionPrompt.objects.filter(
        pk=daily_prompt.pk
    ).update(
        **update_values
    )

    daily_prompt.refresh_from_db()

    return daily_prompt


@transaction.atomic
def prepare_daily_reflection_for_journey_creation(
    *,
    user,
    timezone_name: str | None,
) -> DailyReflectionPromptResult:
    """
    Prepare today's prompt when Journey creation starts.
    """

    normalized_timezone = (
        _normalized_timezone_name(
            timezone_name
        )
    )

    current_local_date = (
        _local_date_for_timezone(
            normalized_timezone
        )
    )

    User = get_user_model()

    User.objects.select_for_update().get(
        pk=user.pk
    )

    _expire_previous_prompts(
        user=user,
        current_local_date=current_local_date,
    )

    daily_prompt = _locked_prompt_for_day(
        user=user,
        local_date=current_local_date,
    )

    if daily_prompt is None:
        try:
            daily_prompt = _create_prompt_for_day(
                user=user,
                local_date=current_local_date,
                timezone_name=normalized_timezone,
            )
        except NoEligibleReflectionQuestionsError as exc:
            logger.warning(
                (
                    "[daily-reflection] no eligible question during "
                    "Journey preparation user_id=%s local_date=%s "
                    "timezone=%s journey_entries=%s "
                    "active_days_in_month=%s"
                ),
                getattr(user, "pk", None),
                current_local_date,
                normalized_timezone,
                exc.journey_entries,
                exc.active_days_in_month,
            )

            return _empty_result(
                reason="no_eligible_reflection_question",
                local_date=current_local_date,
                timezone_name=normalized_timezone,
            )

    resolved = _resolved_existing_prompt(
        user=user,
        daily_prompt=daily_prompt,
        represent_deferred=True,
    )

    if not resolved.should_present:
        return resolved

    daily_prompt = _mark_prompt_presented(
        daily_prompt=daily_prompt
    )

    return _result_from_prompt(
        user=user,
        daily_prompt=daily_prompt,
        should_present=True,
        reason=(
            "new_daily_prompt"
            if daily_prompt.prompt_count == 1
            else (
                "deferred_prompt_represented"
                if daily_prompt.status
                == DailyReflectionPromptStatus.DEFERRED
                else "pending_prompt_represented"
            )
        ),
    )


@transaction.atomic
def resolve_daily_reflection_after_publish(
    *,
    user,
    journey: Journey,
    entry: JourneyEntry,
) -> DailyReflectionPromptResult:
    """
    Attach the Journey source without presenting the prompt.
    """

    if entry.journey_id != journey.pk:
        raise ValueError(
            "Journey entry does not belong to the supplied Journey."
        )

    if (
        journey.owner_user is None
        or journey.owner_user.pk != user.pk
    ):
        return _empty_result(
            reason="journey_owner_mismatch"
        )

    User = get_user_model()

    User.objects.select_for_update().get(
        pk=user.pk
    )

    _expire_previous_prompts(
        user=user,
        current_local_date=journey.local_date,
    )

    daily_prompt = _locked_prompt_for_day(
        user=user,
        local_date=journey.local_date,
    )

    if daily_prompt is None:
        try:
            daily_prompt = _create_prompt_for_day(
                user=user,
                local_date=journey.local_date,
                timezone_name=journey.timezone_name,
            )
        except NoEligibleReflectionQuestionsError as exc:
            logger.warning(
                (
                    "[daily-reflection] no eligible question after "
                    "Journey publish user_id=%s journey_id=%s entry_id=%s "
                    "local_date=%s journey_entries=%s "
                    "active_days_in_month=%s"
                ),
                getattr(user, "pk", None),
                getattr(journey, "pk", None),
                getattr(entry, "pk", None),
                journey.local_date,
                exc.journey_entries,
                exc.active_days_in_month,
            )

            return _empty_result(
                reason="no_eligible_reflection_question",
                local_date=journey.local_date,
                timezone_name=journey.timezone_name,
            )

    update_fields = [
        "updated_at",
    ]

    if daily_prompt.journey_id is None:
        daily_prompt.journey = journey
        update_fields.append(
            "journey"
        )

    if (
        daily_prompt.first_source_entry_id
        is None
    ):
        daily_prompt.first_source_entry = (
            entry
        )
        update_fields.append(
            "first_source_entry"
        )

    daily_prompt.latest_source_entry = entry
    update_fields.append(
        "latest_source_entry"
    )

    daily_prompt.save(
        update_fields=update_fields
    )

    daily_prompt.refresh_from_db()

    return _result_from_prompt(
        user=user,
        daily_prompt=daily_prompt,
        should_present=False,
        reason="journey_source_attached",
    )


@transaction.atomic
def apply_daily_reflection_decision(
    *,
    user,
    prompt_public_id,
    decision: str,
) -> DailyReflectionPromptResult:
    """
    Apply Answer now, Ask later, or Not today.
    """

    valid_decisions = {
        DailyReflectionPromptDecision.ANSWER_NOW,
        DailyReflectionPromptDecision.ASK_LATER,
        DailyReflectionPromptDecision.SKIP_TODAY,
    }

    if decision not in valid_decisions:
        raise ValueError(
            "Unsupported Daily Reflection decision."
        )

    daily_prompt = (
        DailyReflectionPrompt.objects
        .select_for_update()
        .select_related(
            "session",
            "session_question",
            "session_question__question",
        )
        .get(
            user=user,
            public_id=prompt_public_id,
        )
    )

    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.ANSWERED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="already_answered_today",
        )

    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.SKIPPED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="already_skipped_today",
        )

    if (
        daily_prompt.status
        == DailyReflectionPromptStatus.EXPIRED
    ):
        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="daily_prompt_expired",
        )

    now = timezone.now()

    if (
        decision
        == DailyReflectionPromptDecision.ANSWER_NOW
    ):
        if (
            daily_prompt.status
            == DailyReflectionPromptStatus.DEFERRED
        ):
            daily_prompt.status = (
                DailyReflectionPromptStatus.PENDING
            )

            daily_prompt.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=True,
            reason="answer_now",
        )

    if (
        decision
        == DailyReflectionPromptDecision.ASK_LATER
    ):
        daily_prompt.status = (
            DailyReflectionPromptStatus.DEFERRED
        )
        daily_prompt.deferred_count = (
            F("deferred_count") + 1
        )
        daily_prompt.deferred_at = now

        daily_prompt.save(
            update_fields=[
                "status",
                "deferred_count",
                "deferred_at",
                "updated_at",
            ]
        )

        daily_prompt.refresh_from_db()

        return _result_from_prompt(
            user=user,
            daily_prompt=daily_prompt,
            should_present=False,
            reason="deferred_until_next_journey",
        )

    daily_prompt.status = (
        DailyReflectionPromptStatus.SKIPPED
    )
    daily_prompt.skipped_at = now

    daily_prompt.save(
        update_fields=[
            "status",
            "skipped_at",
            "updated_at",
        ]
    )

    if (
        daily_prompt.session.status
        == ReflectionSessionStatus.OPEN
    ):
        daily_prompt.session.status = (
            ReflectionSessionStatus.CANCELLED
        )

        daily_prompt.session.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

    return _result_from_prompt(
        user=user,
        daily_prompt=daily_prompt,
        should_present=False,
        reason="skipped_for_today",
    )


def get_current_daily_reflection_prompt(
    *,
    user,
) -> DailyReflectionPromptResult:
    """
    Return current state without creating a prompt.
    """

    prompt = (
        DailyReflectionPrompt.objects
        .select_related(
            "journey",
            "session",
            "session_question",
            "session_question__question",
        )
        .filter(
            user=user,
            status__in=[
                DailyReflectionPromptStatus.PENDING,
                DailyReflectionPromptStatus.DEFERRED,
                DailyReflectionPromptStatus.SKIPPED,
                DailyReflectionPromptStatus.ANSWERED,
            ],
        )
        .order_by(
            "-local_date",
            "-id",
        )
        .first()
    )

    if prompt is None:
        return _empty_result(
            reason="no_daily_prompt"
        )

    timezone_name = _normalized_timezone_name(
        prompt.timezone_name
    )

    current_local_date = (
        _local_date_for_timezone(
            timezone_name
        )
    )

    if prompt.local_date != current_local_date:
        return _empty_result(
            reason="no_daily_prompt",
            local_date=current_local_date,
            timezone_name=timezone_name,
        )

    return _resolved_existing_prompt(
        user=user,
        daily_prompt=prompt,
        represent_deferred=False,
    )