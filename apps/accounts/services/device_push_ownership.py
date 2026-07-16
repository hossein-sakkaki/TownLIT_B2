# apps/accounts/services/device_push_ownership.py

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from apps.accounts.models.devices import UserDeviceKey


User = get_user_model()


@dataclass(frozen=True)
class DeviceOwnershipClaimResult:
    device: UserDeviceKey
    released_count: int


def normalize_device_id(value: str | None) -> str | None:
    """Normalize a canonical device id."""
    cleaned = (value or "").strip().lower()
    return cleaned or None


def normalize_install_id(value: str | None) -> str | None:
    """Normalize a stable app installation id."""
    cleaned = (value or "").strip().lower()
    return cleaned or None


def normalize_platform(value: str | None) -> str | None:
    """Normalize a device platform."""
    cleaned = (value or "").strip().lower()
    return cleaned or None


def normalize_push_token(value: str | None) -> str | None:
    """
    Normalize a push token.

    Push tokens are case-sensitive on some providers.
    Do not lowercase them.
    """
    cleaned = (value or "").strip()
    return cleaned or None


@transaction.atomic
def claim_device_push_ownership(
    *,
    device_pk: int,
) -> DeviceOwnershipClaimResult:
    """
    Make one device row the active owner of its push identity.

    Ownership rules:
    - One active row per push token.
    - One active row per platform + install id.
    - Previous rows stay for key history.
    - Previous rows lose push delivery access.
    """
    device = (
        UserDeviceKey.objects
        .select_for_update()
        .select_related("user")
        .get(pk=device_pk)
    )

    device.device_id = normalize_device_id(device.device_id) or device.device_id
    device.install_id = normalize_install_id(device.install_id)
    device.platform = normalize_platform(device.platform)
    device.push_token = normalize_push_token(device.push_token)

    conflict_filter = Q()

    if device.push_token:
        conflict_filter |= Q(
            push_token=device.push_token,
        )

    if device.install_id:
        if device.platform:
            conflict_filter |= Q(
                install_id=device.install_id,
                platform=device.platform,
            )
        else:
            conflict_filter |= Q(
                install_id=device.install_id,
            )

    released_count = 0

    if conflict_filter:
        conflicts = (
            UserDeviceKey.objects
            .select_for_update()
            .filter(conflict_filter)
            .filter(is_active=True)
            .exclude(pk=device.pk)
        )

        released_count = conflicts.update(
            is_active=False,
            push_token=None,
        )

    device.is_active = True
    device.save(
        update_fields=[
            "device_id",
            "install_id",
            "platform",
            "push_token",
            "is_active",
            "last_used",
        ]
    )

    return DeviceOwnershipClaimResult(
        device=device,
        released_count=released_count,
    )


@transaction.atomic
def release_user_device_push_ownership(
    *,
    user: User,
    device_id: str | None = None,
    install_id: str | None = None,
    push_token: str | None = None,
) -> int:
    """
    Disable push delivery for one user's current device.

    At least one device identifier must be provided.
    """
    normalized_device_id = normalize_device_id(device_id)
    normalized_install_id = normalize_install_id(install_id)
    normalized_push_token = normalize_push_token(push_token)

    identity_filter = Q()

    if normalized_device_id:
        identity_filter |= Q(
            device_id=normalized_device_id,
        )

    if normalized_install_id:
        identity_filter |= Q(
            install_id=normalized_install_id,
        )

    if normalized_push_token:
        identity_filter |= Q(
            push_token=normalized_push_token,
        )

    if not identity_filter:
        return 0

    devices = (
        UserDeviceKey.objects
        .select_for_update()
        .filter(
            user=user,
            is_active=True,
        )
        .filter(identity_filter)
    )

    return devices.update(
        is_active=False,
        push_token=None,
    )