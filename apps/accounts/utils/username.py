# apps/accounts/utils/username.py

import re
import secrets
from typing import Optional

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.text import slugify

from apps.accounts.constants.default_usernames import (
    GUEST_FALLBACK_USERNAME_PREFIX,
    MEMBER_FALLBACK_USERNAME_WORDS,
)
from validators.usernameValidators.username_normalizer import normalize_username
from validators.usernameValidators.username_validator import validate_username_format


RANDOM_SUFFIX_HEX_LENGTH = 4
MAX_RANDOM_ATTEMPTS = 50


def _username_exists(username: str, model_cls) -> bool:
    """
    Check username uniqueness.
    """
    return model_cls.objects.filter(username=username).exists()


def _username_reserved_for_other_user(username: str, user=None) -> bool:
    """
    Check temporary username reservation without hard import cycle.
    """
    try:
        UsernameReservation = apps.get_model("accounts", "UsernameReservation")
    except LookupError:
        return False

    if not UsernameReservation:
        return False

    if user is not None:
        return UsernameReservation.is_reserved_for_other_user(username, user)

    from django.utils import timezone

    return UsernameReservation.objects.filter(
        username=username,
        expires_at__gt=timezone.now(),
    ).exists()


def _is_username_available(username: str, model_cls, user=None) -> bool:
    """
    Validate and check availability.
    """
    try:
        username = validate_username_format(username)
    except ValidationError:
        return False

    if _username_exists(username, model_cls):
        return False

    if _username_reserved_for_other_user(username, user):
        return False

    return True


def _safe_slug_from_email_local_part(email: str) -> str:
    """
    Convert email local-part into a username-like base.
    """
    local_part = email.split("@", 1)[0]

    # Keep dots visually, convert other separators through slugify.
    base = slugify(local_part.replace(".", "-")).replace("-", ".")

    # Normalize lowercase and remove whitespace.
    base = normalize_username(base)

    # Remove repeated dots that may come from unusual email local-parts.
    base = re.sub(r"\.+", ".", base).strip(".")

    return base


def _next_numbered_username(base: str, model_cls, user=None) -> Optional[str]:
    """
    Find the smallest available numbered username for a safe base.
    Example:
      john
      john_1
      john_2
    """
    base = normalize_username(base)

    try:
        validate_username_format(base)
    except ValidationError:
        return None

    if _is_username_available(base, model_cls, user=user):
        return base

    pattern = rf"^{re.escape(base)}_(\d+)$"

    existing = (
        model_cls.objects
        .filter(Q(username=base) | Q(username__regex=pattern))
        .values_list("username", flat=True)
    )

    used = set()

    for username in existing:
        if username == base:
            used.add(0)
            continue

        match = re.fullmatch(pattern, username)
        if match:
            try:
                used.add(int(match.group(1)))
            except ValueError:
                continue

    i = 1
    while i in used:
        i += 1

    candidate = f"{base}_{i}"

    if _is_username_available(candidate, model_cls, user=user):
        return candidate

    return None


def _random_suffix() -> str:
    """
    Generate short unpredictable suffix.
    """
    return secrets.token_hex(RANDOM_SUFFIX_HEX_LENGTH // 2)


def _random_member_base_word() -> str:
    """
    Pick a positive fallback word for members.
    """
    return secrets.choice(MEMBER_FALLBACK_USERNAME_WORDS)


def _fallback_base(is_member: bool) -> str:
    """
    Select fallback base by account type.
    """
    if is_member:
        return _random_member_base_word()

    return GUEST_FALLBACK_USERNAME_PREFIX


def generate_safe_random_username(model_cls, is_member: bool = False, user=None) -> str:
    """
    Generate a safe random username.

    Member:
      blessed_a4f8
      faithful_92bc

    Guest:
      user_a4f8
      user_92bc
    """
    for _ in range(MAX_RANDOM_ATTEMPTS):
        base = _fallback_base(is_member=is_member)
        candidate = f"{base}_{_random_suffix()}"

        candidate = normalize_username(candidate)

        if _is_username_available(candidate, model_cls, user=user):
            return candidate

    # Longer emergency fallback after repeated collisions.
    for _ in range(MAX_RANDOM_ATTEMPTS):
        base = _fallback_base(is_member=is_member)
        candidate = f"{base}_{secrets.token_hex(4)}"

        candidate = normalize_username(candidate)

        if _is_username_available(candidate, model_cls, user=user):
            return candidate

    raise RuntimeError("Could not generate a safe unique username.")


def generate_unique_username_from_email(
    email: str,
    model_cls,
    is_member: bool = False,
    user=None,
) -> str:
    """
    Generate a safe unique username from email.

    If the email local-part creates an unsafe/reserved username,
    fall back to a safe generated username.

    Examples:
      sakkaki.hossein@gmail.com -> sakkaki.hossein
      sakkaki.hossein@yahoo.com -> sakkaki.hossein_1

      admin@gmail.com -> blessed_a4f8 for member
      admin@gmail.com -> user_a4f8 for guest
    """
    if not email or "@" not in email:
        return generate_safe_random_username(
            model_cls=model_cls,
            is_member=is_member,
            user=user,
        )

    base = _safe_slug_from_email_local_part(email)

    if base:
        candidate = _next_numbered_username(
            base=base,
            model_cls=model_cls,
            user=user,
        )

        if candidate:
            return candidate

    return generate_safe_random_username(
        model_cls=model_cls,
        is_member=is_member,
        user=user,
    )