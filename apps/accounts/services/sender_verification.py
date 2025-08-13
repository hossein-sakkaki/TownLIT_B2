# apps/accounts/services/sender_verification.py
from __future__ import annotations
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import UserDeviceKey

# Lightweight cache TTL to avoid hitting DB for every send
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_key(user_id: int, device_id: str) -> str:
    return f"sender_vf:{user_id}:{device_id}"


def is_sender_device_verified(
    user,
    device_id: Optional[str],
    *,
    dialogue_is_group: Optional[bool] = None,
) -> bool:
    """
    Return True if the sender's device is allowed to send messages.

    Policy:
      - If REQUIRE_SENDER_VERIFIED_DMS_ONLY=True in settings, verification is enforced for DMs only.
        Group chats are bypassed (return True) by default.
      - Otherwise, enforce for all dialogues (DMs and groups).
      - If the device is is_verified=True → allowed.
      - Optional grace: if SENDER_VERIFIED_GRACE_MINUTES > 0, newly-registered devices
        may send within the grace window, provided the PoP challenge hasn't expired.

    NOTE: Uses Django cache to reduce DB load; cache is invalidated via signals on UserDeviceKey updates.
    """
    dev_id = (device_id or "").strip().lower()
    if not dev_id:
        return False

    # Enforce only for DMs (default), unless configured otherwise
    enforce_only_dms = getattr(settings, "REQUIRE_SENDER_VERIFIED_DMS_ONLY", True)
    if enforce_only_dms and dialogue_is_group is True:
        return True

    ck = _cache_key(user.id, dev_id)
    cached = cache.get(ck)
    if cached is not None:
        return bool(cached)

    udk = (
        UserDeviceKey.objects
        .filter(user=user, device_id=dev_id, is_active=True)
        .only("is_verified", "created_at", "pop_challenge_expiry")
        .first()
    )
    if not udk:
        cache.set(ck, 0, _CACHE_TTL_SECONDS)
        return False

    # Strict pass: verified device
    if udk.is_verified:
        cache.set(ck, 1, _CACHE_TTL_SECONDS)
        return True

    # Optional grace window for newly-registered devices
    grace_min = int(getattr(settings, "SENDER_VERIFIED_GRACE_MINUTES", 0) or 0)
    if grace_min > 0 and udk.created_at:
        in_grace = (timezone.now() - udk.created_at) <= timedelta(minutes=grace_min)
        not_expired = (udk.pop_challenge_expiry is None) or (timezone.now() <= udk.pop_challenge_expiry)
        if in_grace and not_expired:
            cache.set(ck, 1, _CACHE_TTL_SECONDS)
            return True

    cache.set(ck, 0, _CACHE_TTL_SECONDS)
    return False


def invalidate_sender_verification_cache(user_id: int, device_id: str) -> None:
    """
    Explicitly clear the cache entry when a UserDeviceKey changes (PoP verified,
    rotation, deactivate, etc).
    """
    cache.delete(_cache_key(user_id, (device_id or "").strip().lower()))
