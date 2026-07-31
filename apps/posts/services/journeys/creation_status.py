# apps/posts/services/journeys/creation_status.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.posts.constants.journeys import (
    JOURNEY_MAX_ENTRIES_PER_DAY,
)
from apps.posts.models.journey import Journey
from apps.posts.services.journeys.timezone import (
    local_date_for_timezone,
    resolve_user_timezone_name,
)
from apps.profiles.models.member import Member


@dataclass(frozen=True)
class JourneyCreationStatus:
    """
    Current Journey creation capacity for one owner and local day.
    """

    can_create: bool
    reason: str

    local_date: date
    timezone_name: str

    entry_count: int
    remaining_capacity: int
    max_entries: int

    journey_id: int | None
    journey_slug: str | None

    def as_dict(self) -> dict:
        return {
            "can_create": self.can_create,
            "reason": self.reason,
            "local_date": self.local_date,
            "timezone_name": self.timezone_name,
            "entry_count": self.entry_count,
            "remaining_capacity": self.remaining_capacity,
            "max_entries": self.max_entries,
            "journey_id": self.journey_id,
            "journey_slug": self.journey_slug,
        }


def get_journey_creation_status(
    *,
    user,
    owner,
    requested_timezone: str | None = None,
) -> JourneyCreationStatus:
    """
    Return the authoritative Journey capacity before opening the editor.

    Publish still enforces the daily limit atomically.
    """

    member = _validate_member_owner(
        user=user,
        owner=owner,
    )

    timezone_name = resolve_user_timezone_name(
        user=user,
        requested_timezone=requested_timezone,
    )

    local_date = local_date_for_timezone(
        timezone_name=timezone_name,
        value=timezone.now(),
    )

    member_content_type = ContentType.objects.get_for_model(
        Member,
        for_concrete_model=False,
    )

    journey = (
        Journey.objects
        .filter(
            content_type=member_content_type,
            object_id=member.pk,
            local_date=local_date,
        )
        .only(
            "id",
            "slug",
            "local_date",
            "timezone_name",
        )
        .first()
    )

    if journey is None:
        entry_count = 0
        remaining_capacity = JOURNEY_MAX_ENTRIES_PER_DAY
    else:
        entry_count = journey.entry_count
        remaining_capacity = journey.remaining_capacity

    can_create = remaining_capacity > 0

    return JourneyCreationStatus(
        can_create=can_create,
        reason=(
            "available"
            if can_create
            else "daily_limit_reached"
        ),
        local_date=local_date,
        timezone_name=timezone_name,
        entry_count=entry_count,
        remaining_capacity=remaining_capacity,
        max_entries=JOURNEY_MAX_ENTRIES_PER_DAY,
        journey_id=journey.pk if journey else None,
        journey_slug=journey.slug if journey else None,
    )


def _validate_member_owner(
    *,
    user,
    owner,
) -> Member:
    """
    Keep the preflight gate aligned with Journey publish rules.
    """

    if not user or not user.is_authenticated:
        raise ValidationError(
            "Authentication is required."
        )

    if not user.is_member:
        raise ValidationError(
            {
                "owner": "Only Member users can create Journey.",
            }
        )

    if not isinstance(owner, Member):
        raise ValidationError(
            {
                "owner": (
                    "The active profile must be a Member profile."
                ),
            }
        )

    if owner.user_id != user.pk:
        raise ValidationError(
            {
                "owner": (
                    "Journey owner does not match the authenticated user."
                ),
            }
        )

    if not owner.is_active:
        raise ValidationError(
            {
                "owner": "Member profile is inactive.",
            }
        )

    return owner