# apps/posts/services/journeys/timezone.py

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone


def resolve_user_timezone_name(
    *,
    user,
    requested_timezone: str | None = None,
) -> str:
    """
    Resolve a safe IANA timezone.
    """

    candidates = [
        requested_timezone,
        getattr(user, "timezone", None),
        getattr(user, "timezone_name", None),
        getattr(settings, "TIME_ZONE", None),
        "UTC",
    ]

    for candidate in candidates:
        value = str(candidate or "").strip()

        if not value:
            continue

        try:
            ZoneInfo(value)
            return value
        except ZoneInfoNotFoundError:
            continue

    return "UTC"


def local_date_for_timezone(
    *,
    timezone_name: str,
    value=None,
):
    """
    Return the local calendar date.
    """

    current = value or timezone.now()
    zone = ZoneInfo(timezone_name)

    return current.astimezone(zone).date()