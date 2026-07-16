# apps/accounts/services/username_resolution.py

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.models.username_reservation import (
    UsernameReservation,
)
from validators.usernameValidators.username_normalizer import (
    normalize_username,
)


CustomUser = get_user_model()


@dataclass(frozen=True)
class ResolvedUsername:
    requested_username: str
    canonical_username: str
    user: CustomUser
    was_alias: bool


def resolve_username(
    username: str,
    *,
    include_deleted: bool = False,
) -> ResolvedUsername | None:
    """
    Resolve either a current username or a permanent historical alias.

    Resolution priority:
    1. Current CustomUser.username
    2. Historical UsernameReservation alias

    Current usernames always have priority, although permanent alias
    protection should prevent collisions from being created.
    """

    normalized = normalize_username(
        username or ""
    )

    if not normalized:
        return None

    current_queryset = CustomUser.objects.filter(
        username=normalized
    )

    if not include_deleted:
        current_queryset = current_queryset.filter(
            Q(is_deleted=False)
            | Q(is_deleted__isnull=True)
        )

    current_user = current_queryset.first()

    if current_user is not None:
        return ResolvedUsername(
            requested_username=normalized,
            canonical_username=current_user.username,
            user=current_user,
            was_alias=False,
        )

    alias_queryset = (
        UsernameReservation.objects
        .select_related("user")
        .filter(
            username=normalized,
        )
    )

    if not include_deleted:
        alias_queryset = alias_queryset.filter(
            Q(user__is_deleted=False)
            | Q(user__is_deleted__isnull=True)
        )

    alias = alias_queryset.first()

    if alias is None:
        return None

    return ResolvedUsername(
        requested_username=normalized,
        canonical_username=alias.user.username,
        user=alias.user,
        was_alias=(
            normalized != alias.user.username
        ),
    )