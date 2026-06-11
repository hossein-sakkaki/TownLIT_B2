
# apps/core/security/litshield_access_state.py

import hashlib
import hmac
import re
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


DEFAULT_ACCESS_DURATION = getattr(
    settings,
    "LITSHIELD_ACCESS_EXPIRATION_SECONDS",
    300,
)

ALLOWED_LITSHIELD_SCOPES = {
    "general",
    "conversation",
    "covenant",
}

DEVICE_ID_MAX_LENGTH = 255
DEVICE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-:.]{6,255}$")


def normalize_scope(scope: str | None) -> str:
    value = (scope or "").strip().lower()

    if value not in ALLOWED_LITSHIELD_SCOPES:
        return ""

    return value


def extract_device_id(request) -> str | None:
    """
    Native apps should send X-Device-ID.
    Body/query fallbacks are kept for compatibility, but header is preferred.
    """
    candidates = [
        request.headers.get("X-Device-ID"),
        request.META.get("HTTP_X_DEVICE_ID"),
        getattr(request, "data", {}).get("device_id") if hasattr(request, "data") else None,
        request.query_params.get("device_id") if hasattr(request, "query_params") else None,
    ]

    for raw in candidates:
        if raw is None:
            continue

        value = str(raw).strip().lower()

        if not value:
            continue

        if len(value) > DEVICE_ID_MAX_LENGTH:
            continue

        if not DEVICE_ID_PATTERN.match(value):
            continue

        return value

    return None


def _device_fingerprint(device_id: str) -> str:
    """
    Never store raw device id inside the cache key.
    HMAC protects against predictable/cache-key enumeration.
    """
    secret = getattr(settings, "SECRET_KEY", "")
    return hmac.new(
        secret.encode("utf-8"),
        device_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def litshield_cache_key(*, user_id: int, scope: str, device_id: str) -> str:
    scope = normalize_scope(scope)
    fingerprint = _device_fingerprint(device_id)

    return f"litshield:access:v1:user:{user_id}:scope:{scope}:device:{fingerprint}"


def grant_device_litshield_access(
    *,
    user,
    scope: str,
    device_id: str | None,
    max_age: int = DEFAULT_ACCESS_DURATION,
) -> dict | None:
    scope = normalize_scope(scope)

    if not scope or not user or not getattr(user, "is_authenticated", False):
        return None

    if not device_id:
        return None

    key = litshield_cache_key(
        user_id=user.id,
        scope=scope,
        device_id=device_id,
    )

    expires_at = timezone.now() + timedelta(seconds=max_age)

    payload = {
        "user_id": user.id,
        "scope": scope,
        "device_id_hash": _device_fingerprint(device_id),
        "granted_at": timezone.now().isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    cache.set(key, payload, timeout=max_age)

    return payload


def has_device_litshield_access(*, user, scope: str, device_id: str | None) -> bool:
    scope = normalize_scope(scope)

    if not scope or not user or not getattr(user, "is_authenticated", False):
        return False

    if not device_id:
        return False

    key = litshield_cache_key(
        user_id=user.id,
        scope=scope,
        device_id=device_id,
    )

    return cache.get(key) is not None


def revoke_device_litshield_access(*, user, scope: str, device_id: str | None) -> None:
    scope = normalize_scope(scope)

    if not scope or not user or not getattr(user, "is_authenticated", False):
        return

    if not device_id:
        return

    key = litshield_cache_key(
        user_id=user.id,
        scope=scope,
        device_id=device_id,
    )

    cache.delete(key)


def revoke_many_device_litshield_access(*, user, scopes: list[str], device_id: str | None) -> None:
    if not user or not getattr(user, "is_authenticated", False):
        return

    if not device_id:
        return

    keys = []

    for raw_scope in scopes or []:
        scope = normalize_scope(raw_scope)
        if not scope:
            continue

        keys.append(
            litshield_cache_key(
                user_id=user.id,
                scope=scope,
                device_id=device_id,
            )
        )

    if keys:
        cache.delete_many(keys)