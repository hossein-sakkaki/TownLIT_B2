# apps/core/security/account_gate/service.py

from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.utils.functional import SimpleLazyObject

UserModel = get_user_model()


def is_authenticated_user(user) -> bool:
    """
    Safely check authenticated users across Django/session/JWT contexts.
    """
    if not user:
        return False

    try:
        return bool(user.is_authenticated)
    except Exception:
        return False


def is_restricted_owner_user(user) -> bool:
    """
    Return True only when the authenticated user's own Member profile
    is temporarily restricted.

    This does NOT restrict:
    - guests
    - visitors
    - confidants who restricted someone else
    - normal members
    - paused accounts by themselves
    """
    if not is_authenticated_user(user):
        return False

    if getattr(user, "is_deleted", False):
        return False

    if getattr(user, "is_suspended", False):
        return False

    if not getattr(user, "is_member", False):
        return False

    try:
        from apps.profiles.models.member import Member

        return Member.objects.filter(
            user_id=user.id,
            is_active=True,
            is_hidden_by_confidants=True,
        ).exists()
    except Exception:
        # Fail closed would risk locking users out because of transient errors.
        # Fail open keeps availability; view-level gates still apply.
        return False


def resolve_authenticated_user_from_request(request):
    """
    Resolve user for middleware.

    Django AuthenticationMiddleware may not authenticate JWT Bearer tokens.
    For DRF/SimpleJWT requests, manually authenticate when needed.
    """
    user = getattr(request, "user", None)

    if isinstance(user, SimpleLazyObject):
        try:
            user = user._wrapped if user._wrapped is not None else user
        except Exception:
            pass

    if is_authenticated_user(user):
        return user

    # SimpleJWT fallback.
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication

        result = JWTAuthentication().authenticate(request)

        if result:
            jwt_user, _token = result
            return jwt_user
    except Exception:
        return None

    return None