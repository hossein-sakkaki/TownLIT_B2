# apps/core/security/access.py

import hashlib
import hmac
import re
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response

from apps.accounts.models.devices import UserDeviceKey


DEFAULT_ACCESS_DURATION = settings.LITSHIELD_ACCESS_EXPIRATION_SECONDS

_SCOPE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


# ---------------------------------------------------------------------
# Scope / Device helpers
# ---------------------------------------------------------------------

def normalize_litshield_scope(scope: str | None) -> str | None:
    """
    Keep scope names predictable and safe for cache/cookie keys.
    """
    value = (scope or "").strip().lower()

    if not value:
        return None

    if not _SCOPE_PATTERN.match(value):
        return None

    return value


def get_litshield_grant_scopes(scope: str | None) -> list[str]:
    """
    Return all scopes that should be granted together.

    Example:
    - If scope is "conversation" and shared scopes are
      ["conversation", "covenant"], both will be granted.
    - Unknown/custom scopes remain isolated unless added to settings.
    """
    normalized_scope = normalize_litshield_scope(scope)
    if not normalized_scope:
        return []

    raw_shared = getattr(settings, "LITSHIELD_SHARED_SCOPES", [])
    shared_scopes = []

    for item in raw_shared:
        normalized = normalize_litshield_scope(item)
        if normalized:
            shared_scopes.append(normalized)

    # If this scope belongs to the shared group, grant the full group.
    if normalized_scope in shared_scopes:
        return sorted(set(shared_scopes))

    # Otherwise only grant the requested scope.
    return [normalized_scope]


def get_request_device_id(request) -> str | None:
    """
    Canonical device id accessor.

    Priority:
    1) X-Device-ID header
    2) body device_id
    3) query device_id

    Mobile clients should send X-Device-ID.
    Web can continue relying on secure cookie flow.
    """
    candidates = [
        request.headers.get("X-Device-ID"),
        getattr(request, "data", {}).get("device_id") if hasattr(request, "data") else None,
        request.query_params.get("device_id") if hasattr(request, "query_params") else None,
    ]

    for candidate in candidates:
        if not candidate:
            continue

        value = str(candidate).strip().lower()
        if value:
            return value

    return None


def get_client_ip(request) -> str:
    """
    Used only for rate-limit fallback when no device id exists.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR", "unknown")


def is_registered_active_device(user, device_id: str | None) -> bool:
    """
    Verify that X-Device-ID belongs to this authenticated user
    and is currently active.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if not device_id:
        return False

    return UserDeviceKey.objects.filter(
        user=user,
        device_id=device_id.strip().lower(),
        is_active=True,
    ).exists()


def _hmac_digest(value: str) -> str:
    """
    Avoid storing raw user/device identifiers in cache keys.
    """
    secret = settings.SECRET_KEY.encode("utf-8")
    payload = value.encode("utf-8")

    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _access_cache_key(*, scope: str, user_id: int, device_id: str) -> str:
    raw = f"litshield:access:{scope}:u:{user_id}:d:{device_id}"
    return "litshield:access:" + _hmac_digest(raw)


def _pin_attempt_cache_key(*, scope: str, user_id: int, device_or_ip: str) -> str:
    raw = f"litshield:pin_attempts:{scope}:u:{user_id}:x:{device_or_ip}"
    return "litshield:pin_attempts:" + _hmac_digest(raw)


def _pin_lock_cache_key(*, scope: str, user_id: int, device_or_ip: str) -> str:
    raw = f"litshield:pin_lock:{scope}:u:{user_id}:x:{device_or_ip}"
    return "litshield:pin_lock:" + _hmac_digest(raw)


def _rate_limit_identity(request, user, scope: str) -> str:
    """
    Rate-limit by user + scope + device when available.
    If no device id exists, fallback to client IP.
    """
    device_id = get_request_device_id(request)
    if device_id:
        return f"device:{device_id}"

    return f"ip:{get_client_ip(request)}"


# ---------------------------------------------------------------------
# PIN brute-force protection
# ---------------------------------------------------------------------

def get_litshield_pin_lock_status(*, request, user, scope: str) -> dict:
    """
    Return lock status for this user/scope/device-or-ip.
    """
    identity = _rate_limit_identity(request, user, scope)

    lock_key = _pin_lock_cache_key(
        scope=scope,
        user_id=user.id,
        device_or_ip=identity,
    )

    locked_until_iso = cache.get(lock_key)

    if not locked_until_iso:
        return {
            "locked": False,
            "locked_until": None,
            "remaining_seconds": 0,
        }

    locked_until = None

    try:
        locked_until = timezone.datetime.fromisoformat(locked_until_iso)
        if timezone.is_naive(locked_until):
            locked_until = timezone.make_aware(locked_until)
    except Exception:
        cache.delete(lock_key)
        return {
            "locked": False,
            "locked_until": None,
            "remaining_seconds": 0,
        }

    remaining = int((locked_until - timezone.now()).total_seconds())

    if remaining <= 0:
        cache.delete(lock_key)
        return {
            "locked": False,
            "locked_until": None,
            "remaining_seconds": 0,
        }

    return {
        "locked": True,
        "locked_until": locked_until.isoformat(),
        "remaining_seconds": remaining,
    }


def record_litshield_pin_failure(*, request, user, scope: str) -> dict:
    """
    Increment failed PIN counter.
    Lock temporarily if max attempts is reached.
    """
    identity = _rate_limit_identity(request, user, scope)

    attempts_key = _pin_attempt_cache_key(
        scope=scope,
        user_id=user.id,
        device_or_ip=identity,
    )

    lock_key = _pin_lock_cache_key(
        scope=scope,
        user_id=user.id,
        device_or_ip=identity,
    )

    max_attempts = int(getattr(settings, "LITSHIELD_PIN_MAX_FAILED_ATTEMPTS", 5))
    lockout_seconds = int(getattr(settings, "LITSHIELD_PIN_LOCKOUT_SECONDS", 900))

    attempts = cache.get(attempts_key, 0) + 1
    cache.set(attempts_key, attempts, timeout=lockout_seconds)

    attempts_remaining = max(max_attempts - attempts, 0)

    if attempts >= max_attempts:
        locked_until = timezone.now() + timedelta(seconds=lockout_seconds)

        cache.set(
            lock_key,
            locked_until.isoformat(),
            timeout=lockout_seconds,
        )

        cache.delete(attempts_key)

        return {
            "locked": True,
            "locked_until": locked_until.isoformat(),
            "remaining_seconds": lockout_seconds,
            "attempts_remaining": 0,
        }

    return {
        "locked": False,
        "locked_until": None,
        "remaining_seconds": 0,
        "attempts_remaining": attempts_remaining,
    }


def clear_litshield_pin_failures(*, request, user, scope: str):
    """
    Clear failure counters after successful PIN.
    """
    identity = _rate_limit_identity(request, user, scope)

    attempts_key = _pin_attempt_cache_key(
        scope=scope,
        user_id=user.id,
        device_or_ip=identity,
    )

    lock_key = _pin_lock_cache_key(
        scope=scope,
        user_id=user.id,
        device_or_ip=identity,
    )

    cache.delete(attempts_key)
    cache.delete(lock_key)


# ---------------------------------------------------------------------
# Access grant / revoke / check
# ---------------------------------------------------------------------
def grant_litshield_access(
    scope: str,
    user,
    request=None,
    response_data: dict | None = None,
    max_age: int = DEFAULT_ACCESS_DURATION,
):
    """
    Grant LITShield access.

    Web:
    - sets secure HttpOnly cookies for all linked granted scopes.

    Mobile:
    - if X-Device-ID is present and registered, also stores server-side
      user/scope/device grants for all linked granted scopes.
    """
    normalized_scope = normalize_litshield_scope(scope)
    grant_scopes = get_litshield_grant_scopes(normalized_scope)

    expires = timezone.now() + timedelta(seconds=max_age)

    data = {
        "access_granted": True,
        "scope": normalized_scope,
        "granted_scopes": grant_scopes,
        "expires_at": expires.isoformat(),
        "pin_security_enabled": getattr(user, "pin_security_enabled", False),
    }

    if response_data:
        data.update(response_data)

    response = Response(data, status=200)

    # Web/browser cookie support for every linked scope.
    for granted_scope in grant_scopes:
        response.set_cookie(
            f"{granted_scope}_access",
            "granted",
            max_age=max_age,
            httponly=True,
            secure=getattr(settings, "SESSION_COOKIE_SECURE", True),
            samesite="Lax",
            path="/",
        )

    # Mobile/device-bound support for every linked scope.
    if request is not None:
        device_id = get_request_device_id(request)

        if device_id and is_registered_active_device(user, device_id):
            for granted_scope in grant_scopes:
                cache.set(
                    _access_cache_key(
                        scope=granted_scope,
                        user_id=user.id,
                        device_id=device_id,
                    ),
                    "granted",
                    timeout=max_age,
                )

            data["device_bound"] = True
            data["device_id"] = device_id
            response.data = data

    return response


def revoke_litshield_access(scope: str, request=None, user=None):
    """
    Revoke access for current cookie/device when possible.
    """
    scope = normalize_litshield_scope(scope)

    response = Response({"message": f"{scope} access revoked"}, status=200)

    response.delete_cookie(
        f"{scope}_access",
        path="/",
        samesite="Lax",
    )

    if request is not None and user is not None and getattr(user, "is_authenticated", False):
        device_id = get_request_device_id(request)

        if device_id:
            cache.delete(
                _access_cache_key(
                    scope=scope,
                    user_id=user.id,
                    device_id=device_id,
                )
            )

    return response


def has_litshield_access(scope: str, request) -> bool:
    """
    Shared access check for decorators.

    Passes if:
    - PIN security is disabled, OR
    - secure cookie says granted, OR
    - registered device has active server-side grant.
    """
    scope = normalize_litshield_scope(scope)
    user = getattr(request, "user", None)

    if not scope:
        return False

    if not user or not getattr(user, "is_authenticated", False):
        return False

    if not getattr(user, "pin_security_enabled", False):
        return True

    # Web/browser path
    if request.COOKIES.get(f"{scope}_access") == "granted":
        return True

    # Mobile/device-bound path
    device_id = get_request_device_id(request)
    if not device_id:
        return False

    if getattr(settings, "LITSHIELD_REQUIRE_REGISTERED_DEVICE_FOR_HEADER_ACCESS", True):
        if not is_registered_active_device(user, device_id):
            return False

    return cache.get(
        _access_cache_key(
            scope=scope,
            user_id=user.id,
            device_id=device_id,
        )
    ) == "granted"


def check_litshield_access(scope: str, request):
    """
    Return current access state for web/mobile clients.
    """
    scope = normalize_litshield_scope(scope)
    user = getattr(request, "user", None)

    if not scope:
        return Response({
            "access_granted": False,
            "pin_security_enabled": None,
            "expires_at": None,
            "error": "Invalid scope.",
        })

    if user is None or not user.is_authenticated:
        return Response({
            "access_granted": False,
            "pin_security_enabled": None,
            "expires_at": None,
        })

    if not getattr(user, "pin_security_enabled", False):
        return Response({
            "access_granted": False,
            "pin_security_enabled": False,
            "expires_at": None,
        })

    if has_litshield_access(scope, request):
        expires = timezone.now() + timedelta(seconds=DEFAULT_ACCESS_DURATION)

        return Response({
            "access_granted": True,
            "pin_security_enabled": True,
            "expires_at": expires.isoformat(),
        })

    return Response({
        "access_granted": False,
        "pin_security_enabled": True,
        "expires_at": None,
    })
    

