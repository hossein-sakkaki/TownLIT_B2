# apps/core/websocket/access_auth.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-23.
# Last Update by Hossein Sakkaki on 2026-11-02.

import logging

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models.devices import UserDeviceKey
from apps.core.security.account_gate.service import (
    is_restricted_owner_user,
)


logger = logging.getLogger(__name__)

MAX_ACCESS_TOKEN_LENGTH = 8192
User = get_user_model()


def _account_allows_websocket(user):
    """One account policy reused at authentication and session recheck."""
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and not getattr(user, "is_deleted", False)
        and not getattr(user, "is_suspended", False)
        and not is_restricted_owner_user(user, fail_closed=True)
    )


def validate_access_token_for_websocket(raw_token):
    """
    Validate a WebSocket access token and its account.

    This function runs in a synchronous database context.
    Never log the raw token or authentication message.
    """
    if (
        not isinstance(raw_token, str)
        or not raw_token
        or len(raw_token) > MAX_ACCESS_TOKEN_LENGTH
    ):
        return None

    try:
        validated_token = AccessToken(raw_token)
        user = JWTAuthentication().get_user(validated_token)

        if not _account_allows_websocket(user):
            return None

        return user

    except Exception:
        # Fail closed without logging credentials or message contents.
        logger.warning(
            "[WS AUTH V2] Authentication rejected or unavailable"
        )
        return None


authenticate_websocket_access_token = database_sync_to_async(
    validate_access_token_for_websocket
)


def validate_websocket_session_access(user_id: int, device_id: str) -> bool:
    """Recheck mutable account and registered-device state for V2."""
    if not isinstance(user_id, int) or user_id <= 0 or not device_id:
        return False

    try:
        user = User.objects.get(pk=user_id)
        if not _account_allows_websocket(user):
            return False

        return UserDeviceKey.objects.filter(
            user_id=user_id,
            device_id=device_id,
            is_active=True,
        ).exists()
    except User.DoesNotExist:
        return False
    except Exception:
        # Fail closed if the database or account policy is unavailable.
        logger.warning("[WS AUTH V2] Session revalidation unavailable")
        return False


check_websocket_session_access = database_sync_to_async(
    validate_websocket_session_access
)
