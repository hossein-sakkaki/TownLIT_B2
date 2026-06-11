# apps/accounts/services/age_policy.py

from __future__ import annotations

from datetime import date

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.constants.user_labels import (
    MIN_STANDARD_ACCOUNT_AGE,
    UNDER_MINIMUM_STANDARD_ACCOUNT_AGE_MESSAGE,
)


def calculate_age(
    birthday: date,
    *,
    today: date | None = None,
) -> int:
    """
    Calculate age from date of birth.

    Uses local date by default so the result matches the app/server timezone.
    """
    today = today or timezone.localdate()

    return (
        today.year
        - birthday.year
        - ((today.month, today.day) < (birthday.month, birthday.day))
    )


def is_standard_account_age(
    birthday: date,
    *,
    today: date | None = None,
) -> bool:
    return calculate_age(birthday, today=today) >= MIN_STANDARD_ACCOUNT_AGE


def validate_standard_account_birthday(
    birthday: date | None,
) -> date | None:
    """
    Validate birthday for the currently available standard account system.

    Protected younger accounts are not available yet, so users under the
    configured minimum age cannot set a standard-account birthday.
    """
    if birthday is None:
        return birthday

    today = timezone.localdate()

    if birthday > today:
        raise serializers.ValidationError(
            {
                "error": "Birthday cannot be in the future.",
                "code": "birthday_in_future",
            }
        )

    if not is_standard_account_age(birthday, today=today):
        raise serializers.ValidationError(
            {
                "error": UNDER_MINIMUM_STANDARD_ACCOUNT_AGE_MESSAGE,
                "code": "under_minimum_standard_account_age",
                "minimum_age": MIN_STANDARD_ACCOUNT_AGE,
            }
        )

    return birthday