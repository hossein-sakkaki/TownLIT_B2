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

    Push tokens are case-sensitive and must never be lowercased.
    """
    cleaned = (value or "").strip()
    return cleaned or None


@transaction.atomic
def claim_device_push_ownership(
    *,
    device_pk: int,
) -> DeviceOwnershipClaimResult:
    """
    Make one device row the active owner of its installation and push identity.

    Ownership rules:
    - one active row per push token;
    - one active row per platform + install id;
    - previous rows stay for key/history purposes;
    - previous owners lose Push delivery access;
    - canonical encryption identity remains separate from Push token validity.
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
        active_conflict_ids = list(
            UserDeviceKey.objects
            .select_for_update()
            .filter(conflict_filter)
            .filter(is_active=True)
            .exclude(pk=device.pk)
            .values_list("pk", flat=True)
        )

        if active_conflict_ids:
            released_count = (
                UserDeviceKey.objects
                .filter(pk__in=active_conflict_ids)
                .update(
                    is_active=False,
                    push_token=None,
                )
            )

        # Historical rows must not retain an owned Push credential.
        inactive_conflict_ids = list(
            UserDeviceKey.objects
            .select_for_update()
            .filter(conflict_filter)
            .filter(is_active=False)
            .exclude(pk=device.pk)
            .exclude(push_token__isnull=True)
            .exclude(push_token__exact="")
            .values_list("pk", flat=True)
        )

        if inactive_conflict_ids:
            (
                UserDeviceKey.objects
                .filter(pk__in=inactive_conflict_ids)
                .update(push_token=None)
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
    Release the current device for one user.

    Identity precedence:
    1) device_id
    2) install_id
    3) push_token

    This avoids accidentally releasing multiple devices when the client
    submits a stale Push token together with a valid canonical device id.
    """
    normalized_device_id = normalize_device_id(device_id)
    normalized_install_id = normalize_install_id(install_id)
    normalized_push_token = normalize_push_token(push_token)

    devices = (
        UserDeviceKey.objects
        .select_for_update()
        .filter(
            user=user,
            is_active=True,
        )
    )

    if normalized_device_id:
        devices = devices.filter(
            device_id=normalized_device_id,
        )

    elif normalized_install_id:
        devices = devices.filter(
            install_id=normalized_install_id,
        )

    elif normalized_push_token:
        devices = devices.filter(
            push_token=normalized_push_token,
        )

    else:
        return 0

    return devices.update(
        is_active=False,
        push_token=None,
    )