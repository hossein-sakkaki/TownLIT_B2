# apps/core/visibility/selectors.py
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import CustomUser


# ------------------------------------------------------------------
# Profile privacy
# ------------------------------------------------------------------

def is_profile_private(owner) -> bool:
    """
    Checks whether the owner's profile is private.

    Assumptions based on your models:
    - Member / GuestUser / Organization may expose `is_private`
    - If attribute does not exist → default PUBLIC
    """
    try:
        return bool(getattr(owner, "is_private", False))
    except Exception:
        return False


# ------------------------------------------------------------------
# Friendship logic (based on apps.profiles.models.Friendship)
# ------------------------------------------------------------------

def are_friends(viewer: Optional[CustomUser], owner) -> bool:
    """
    True if viewer and owner.user have an ACTIVE + ACCEPTED friendship.

    Uses:
      Friendship.status
      Friendship.is_active
    """
    if not viewer or not hasattr(owner, "user"):
        return False

    try:
        from apps.profiles.models import Friendship

        return Friendship.objects.filter(
            is_active=True,
            status="accepted",
            from_user=viewer,
            to_user=owner.user,
        ).exists() or Friendship.objects.filter(
            is_active=True,
            status="accepted",
            from_user=owner.user,
            to_user=viewer,
        ).exists()

    except Exception:
        return False


# ------------------------------------------------------------------
# LITCovenant / Fellowship logic
# ------------------------------------------------------------------

def is_in_covenant(viewer: Optional[CustomUser], owner) -> bool:
    """
    True if viewer and owner.user have an ACCEPTED Fellowship relationship.

    Fellowship is directional but covenant is considered symmetric
    once status is accepted.
    """
    if not viewer or not hasattr(owner, "user"):
        return False

    try:
        from apps.profiles.models import Fellowship

        return Fellowship.objects.filter(
            status="Accepted",
            from_user=viewer,
            to_user=owner.user,
        ).exists() or Fellowship.objects.filter(
            status="Accepted",
            from_user=owner.user,
            to_user=viewer,
        ).exists()

    except Exception:
        return False
