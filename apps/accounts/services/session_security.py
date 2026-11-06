# apps/accounts/services/session_security.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Transaction-safe session generation storage.

This module does not alter JWTs or authentication yet. Callers must perform
password changes and generation increments in the *same* outer transaction
before enabling revocation enforcement.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models.session_security import UserAuthSessionState


User = get_user_model()


def get_session_generation(user_id: int) -> int:
    """Read the current generation; missing rows deliberately mean zero.

    A database error must propagate: authentication enforcement must fail
    closed rather than returning generation zero after an outage.
    """
    generation = (
        UserAuthSessionState.objects
        .filter(user_id=user_id)
        .values_list("generation", flat=True)
        .first()
    )
    return int(generation) if generation is not None else 0


def increment_session_generation(user_id: int) -> int:
    """Atomically invalidate generations below the returned one.

    Serialize increments through the authoritative user row, including
    concurrent first-time creation of the session-state row. Do not call
    from outside the same transaction as the triggering password change.
    """
    with transaction.atomic():
        User.objects.select_for_update().only("pk").get(pk=user_id)
        now = timezone.now()
        state, created = UserAuthSessionState.objects.get_or_create(
            user_id=user_id,
            defaults={"generation": 1, "last_revoked_at": now},
        )
        if not created:
            state.generation += 1
            state.last_revoked_at = now
            state.save(update_fields=("generation", "last_revoked_at", "updated_at"))
        return int(state.generation)
