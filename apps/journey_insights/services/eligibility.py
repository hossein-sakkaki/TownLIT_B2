# apps/journey_insights/services/eligibility.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.utils import timezone

from apps.journey_insights.constants import (
    REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
    ReflectionSessionStatus,
)
from apps.journey_insights.models import ReflectionSession
from apps.journey_insights.services.reflections import (
    _journey_activity_for_user,
)


class ReflectionEligibilityReason:
    ELIGIBLE = "eligible"
    OPEN_SESSION_EXISTS = "open_session_exists"
    MEMBER_PROFILE_REQUIRED = "member_profile_required"
    JOURNEY_REQUIRED = "journey_required"
    ACTIVE_JOURNEY_DAY_REQUIRED = "active_journey_day_required"


@dataclass(frozen=True)
class ReflectionEligibilityResult:
    is_available: bool
    can_start_new_session: bool
    has_open_session: bool
    reason: str
    recommended_question_count: int
    journey_entries: int
    active_days_in_month: int
    open_session_public_id: UUID | None = None
    open_session_expires_at: datetime | None = None

    def as_dict(self) -> dict:
        return {
            "is_available": self.is_available,
            "can_start_new_session": self.can_start_new_session,
            "has_open_session": self.has_open_session,
            "reason": self.reason,
            "recommended_question_count": self.recommended_question_count,
            "journey_entries": self.journey_entries,
            "active_days_in_month": self.active_days_in_month,
            "open_session_public_id": self.open_session_public_id,
            "open_session_expires_at": self.open_session_expires_at,
        }


def _current_open_session(*, user) -> ReflectionSession | None:
    now = timezone.now()

    return (
        ReflectionSession.objects
        .filter(
            user=user,
            status=ReflectionSessionStatus.OPEN,
            expires_at__gt=now,
        )
        .order_by("-opened_at", "-id")
        .first()
    )


def get_reflection_eligibility(*, user) -> ReflectionEligibilityResult:
    """
    Resolve the current Journey Reflection availability for one user.
    """

    activity = _journey_activity_for_user(user=user)

    journey_entries = int(activity.get("journey_entries") or 0)
    active_days_in_month = int(activity.get("active_days_in_month") or 0)

    if not activity.get("has_member_profile"):
        return ReflectionEligibilityResult(
            is_available=False,
            can_start_new_session=False,
            has_open_session=False,
            reason=ReflectionEligibilityReason.MEMBER_PROFILE_REQUIRED,
            recommended_question_count=REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
            journey_entries=0,
            active_days_in_month=0,
        )

    open_session = _current_open_session(user=user)

    if open_session is not None:
        return ReflectionEligibilityResult(
            is_available=True,
            can_start_new_session=False,
            has_open_session=True,
            reason=ReflectionEligibilityReason.OPEN_SESSION_EXISTS,
            recommended_question_count=open_session.question_count or REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
            journey_entries=journey_entries,
            active_days_in_month=active_days_in_month,
            open_session_public_id=open_session.public_id,
            open_session_expires_at=open_session.expires_at,
        )

    if journey_entries < 1:
        return ReflectionEligibilityResult(
            is_available=False,
            can_start_new_session=False,
            has_open_session=False,
            reason=ReflectionEligibilityReason.JOURNEY_REQUIRED,
            recommended_question_count=REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
            journey_entries=journey_entries,
            active_days_in_month=active_days_in_month,
        )

    if active_days_in_month < 1:
        return ReflectionEligibilityResult(
            is_available=False,
            can_start_new_session=False,
            has_open_session=False,
            reason=ReflectionEligibilityReason.ACTIVE_JOURNEY_DAY_REQUIRED,
            recommended_question_count=REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
            journey_entries=journey_entries,
            active_days_in_month=active_days_in_month,
        )

    return ReflectionEligibilityResult(
        is_available=True,
        can_start_new_session=True,
        has_open_session=False,
        reason=ReflectionEligibilityReason.ELIGIBLE,
        recommended_question_count=REFLECTION_DEFAULT_QUESTIONS_PER_SESSION,
        journey_entries=journey_entries,
        active_days_in_month=active_days_in_month,
    )