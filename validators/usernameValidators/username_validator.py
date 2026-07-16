# validators/usernameValidators/username_validator.py

import re

from django.core.exceptions import ValidationError

from validators.usernameValidators.constants import (
    MIN_USERNAME_LENGTH,
    MAX_USERNAME_LENGTH,
    USERNAME_ALLOWED_PATTERN,
    RESERVED_USERNAMES,
    RESERVED_FRAGMENTS,
    BLOCKED_WORDS,
    SCAM_IMPERSONATION_WORDS,
    SACRED_USERNAMES,
)
from validators.usernameValidators.username_normalizer import (
    normalize_username,
    compact_username,
)


def validate_username_format(
    value: str | None,
) -> str:
    """
    Validate and return a normalized TownLIT username.

    Final format:
    - 5...20 characters;
    - lowercase English letters and numbers;
    - zero or one underscore;
    - underscore may only separate two alphanumeric sections;
    - dots, hyphens, spaces and other symbols are not allowed.

    Valid examples:
        hossein
        hossein_sakkaki
        user2026

    Invalid examples:
        _hossein
        hossein_
        hossein__sakkaki
        hossein_sak_kaki
        hossein.sakkaki
        hossein-sakkaki
    """

    username = normalize_username(value)
    compact = compact_username(username)

    if not username:
        raise ValidationError(
            "Username is required.",
            code="required",
        )

    if len(username) < MIN_USERNAME_LENGTH:
        raise ValidationError(
            (
                f"Username must be at least "
                f"{MIN_USERNAME_LENGTH} characters."
            ),
            code="too_short",
        )

    if len(username) > MAX_USERNAME_LENGTH:
        raise ValidationError(
            (
                f"Username must be "
                f"{MAX_USERNAME_LENGTH} characters or less."
            ),
            code="too_long",
        )

    if not re.fullmatch(
        USERNAME_ALLOWED_PATTERN,
        username,
    ):
        raise ValidationError(
            (
                "Username can only contain lowercase letters, numbers, "
                "and one optional underscore between words."
            ),
            code="invalid_format",
        )

    reserved_compact = {
        compact_username(word)
        for word in RESERVED_USERNAMES
    }

    if (
        username in RESERVED_USERNAMES
        or compact in reserved_compact
    ):
        raise ValidationError(
            "This username is reserved and cannot be used.",
            code="reserved_username",
        )

    for fragment in RESERVED_FRAGMENTS:
        fragment_compact = compact_username(
            fragment
        )

        if fragment_compact in compact:
            raise ValidationError(
                (
                    "Username cannot reference TownLIT system, admin, "
                    "support, or verified identities."
                ),
                code="reserved_identity_fragment",
            )

    for word in BLOCKED_WORDS:
        word_compact = compact_username(
            word
        )

        if (
            word in username
            or word_compact in compact
        ):
            raise ValidationError(
                (
                    "Username contains inappropriate "
                    "or unsafe language."
                ),
                code="inappropriate_username",
            )

    for word in SCAM_IMPERSONATION_WORDS:
        word_compact = compact_username(
            word
        )

        if (
            word in username
            or word_compact in compact
        ):
            raise ValidationError(
                (
                    "Username cannot impersonate brands, payment "
                    "services, or trusted institutions."
                ),
                code="impersonation_risk",
            )

    sacred_compact = {
        compact_username(word)
        for word in SACRED_USERNAMES
    }

    if (
        username in SACRED_USERNAMES
        or compact in sacred_compact
    ):
        raise ValidationError(
            (
                "Using sacred names alone is not allowed. "
                "Please use a meaningful phrase."
            ),
            code="sacred_name_alone",
        )

    return username