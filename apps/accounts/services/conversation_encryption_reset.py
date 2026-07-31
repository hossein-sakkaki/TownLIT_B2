#
#  apps/accounts/services/conversation_encryption_reset.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-28.
#  Last Update by Hossein Sakkaki on 2026-07-28.
#

import base64
import re
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models.devices import (
    UserDeviceKey,
    UserDeviceKeyBackup,
    UserSecurityProfile,
)
from apps.accounts.services.device_push_ownership import (
    claim_device_push_ownership,
    normalize_device_id,
    normalize_install_id,
    normalize_platform,
    normalize_push_token,
)
from apps.core.crypto import rsa as crsa
from utils.common.ip import get_client_ip, get_location_from_ip


class ConversationEncryptionResetError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
    ):
        super().__init__(message)

        self.message = message
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ConversationEncryptionResetResult:
    device: UserDeviceKey
    pop_payload: dict
    location: dict
    removed_device_count: int
    removed_backup_count: int
    push_ownership_released: int

    def as_dict(self) -> dict:
        return {
            "message": "Encryption identity reset successfully.",
            "created": True,
            "rotated": True,
            "location": self.location,
            "pop": self.pop_payload,
            "dedup_removed": [],
            "push_ownership_released": self.push_ownership_released,
            "removed_device_count": self.removed_device_count,
            "removed_backup_count": self.removed_backup_count,
            "identity_reset": True,
        }


def reset_conversation_encryption_identity(
    *,
    request,
    user,
) -> ConversationEncryptionResetResult:
    """
    Replace the account encryption identity atomically.

    Existing encrypted messages are not rewrapped because the new private
    key cannot decrypt content encrypted for the previous identity.
    """

    account_password = str(
        request.data.get("account_password") or ""
    )

    confirmation = str(
        request.data.get("confirmation") or ""
    ).strip()

    if not account_password:
        raise ConversationEncryptionResetError(
            "Your TownLIT account password is required.",
            code="ACCOUNT_PASSWORD_REQUIRED",
            status_code=400,
        )

    if not user.check_password(account_password):
        raise ConversationEncryptionResetError(
            "The TownLIT account password is incorrect.",
            code="ACCOUNT_PASSWORD_INVALID",
            status_code=403,
        )

    if confirmation != "RESET":
        raise ConversationEncryptionResetError(
            'Enter "RESET" to confirm the encryption identity reset.',
            code="RESET_CONFIRMATION_INVALID",
            status_code=400,
        )

    device_id = normalize_device_id(
        request.data.get("device_id")
    )

    body_install_id = normalize_install_id(
        request.data.get("install_id")
    )

    header_install_id = normalize_install_id(
        request.headers.get("X-Install-ID")
    )

    install_id = body_install_id or header_install_id

    header_device_id = normalize_device_id(
        request.headers.get("X-Device-ID")
    )

    public_key = str(
        request.data.get("public_key") or ""
    ).strip()

    device_name = str(
        request.data.get("device_name") or ""
    ).strip() or None

    fingerprint_hint = str(
        request.data.get("fingerprint_hint") or ""
    ).strip() or None

    push_token = normalize_push_token(
        request.data.get("push_token")
    )

    platform = normalize_platform(
        request.data.get("platform")
    )

    if not device_id:
        raise ConversationEncryptionResetError(
            "Device ID is required.",
            code="DEVICE_ID_REQUIRED",
            status_code=400,
        )

    if not public_key:
        raise ConversationEncryptionResetError(
            "Public key is required.",
            code="PUBLIC_KEY_REQUIRED",
            status_code=400,
        )

    if header_device_id and header_device_id != device_id:
        raise ConversationEncryptionResetError(
            "X-Device-ID mismatch.",
            code="DEVICE_ID_MISMATCH",
            status_code=400,
        )

    if (
        body_install_id
        and header_install_id
        and body_install_id != header_install_id
    ):
        raise ConversationEncryptionResetError(
            "X-Install-ID mismatch.",
            code="INSTALL_ID_MISMATCH",
            status_code=400,
        )

    if not _is_valid_public_key_pem(public_key):
        raise ConversationEncryptionResetError(
            "Invalid public key format.",
            code="INVALID_PUBLIC_KEY",
            status_code=400,
        )

    ip_address = get_client_ip(request)
    location = get_location_from_ip(ip_address) or {}

    pop_ttl_minutes = _positive_setting_int(
        "POP_TTL_MINUTES",
        fallback=10,
    )

    nonce = crsa.randbytes(32)

    try:
        ciphertext = crsa.rsa_oaep_encrypt_with_public_pem(
            public_key,
            nonce,
        )
    except Exception as exc:
        raise ConversationEncryptionResetError(
            "The new public key could not be validated.",
            code="PUBLIC_KEY_ENCRYPTION_FAILED",
            status_code=400,
        ) from exc

    pop_expiry = timezone.now() + timedelta(
        minutes=pop_ttl_minutes
    )

    with transaction.atomic():
        locked_devices = UserDeviceKey.objects.select_for_update().filter(
            user=user
        )

        locked_backups = UserDeviceKeyBackup.objects.select_for_update().filter(
            user=user
        )

        removed_device_count = locked_devices.count()
        removed_backup_count = locked_backups.count()

        locked_backups.delete()
        locked_devices.delete()

        security_profile, _ = (
            UserSecurityProfile.objects
            .select_for_update()
            .get_or_create(user=user)
        )

        security_profile.has_passphrase = False
        security_profile.save(
            update_fields=[
                "has_passphrase",
                "updated_at",
            ]
        )

        device = UserDeviceKey.objects.create(
            user=user,
            device_id=device_id,
            public_key=public_key,
            device_name=device_name,
            user_agent=request.META.get(
                "HTTP_USER_AGENT",
                "",
            ) or "",
            ip_address=ip_address,
            is_active=True,
            location_city=location.get("city"),
            location_region=location.get("region"),
            location_country=location.get("country"),
            timezone=location.get("timezone"),
            organization=location.get("org"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            postal_code=location.get("postal"),
            install_id=install_id,
            fp_hint=fingerprint_hint,
            push_token=push_token,
            platform=platform,
            is_verified=False,
            verified_at=None,
            pop_challenge_hash=crsa.sha256_bytes(nonce),
            pop_challenge_expiry=pop_expiry,
            pop_attempts=0,
        )

        claim_result = claim_device_push_ownership(
            device_pk=device.pk,
        )

        device = claim_result.device

    pop_payload = {
        "ciphertext_b64": crsa.b64e(ciphertext),
        "expires_at": pop_expiry.isoformat(),
        "ttl_minutes": pop_ttl_minutes,
    }

    return ConversationEncryptionResetResult(
        device=device,
        pop_payload=pop_payload,
        location=location,
        removed_device_count=removed_device_count,
        removed_backup_count=removed_backup_count,
        push_ownership_released=claim_result.released_count,
    )


def _is_valid_public_key_pem(
    public_key: str,
) -> bool:
    if (
        "-----BEGIN PUBLIC KEY-----" not in public_key
        or "-----END PUBLIC KEY-----" not in public_key
    ):
        return False

    cleaned = re.sub(
        r"-----(BEGIN|END) PUBLIC KEY-----|\s+",
        "",
        public_key,
    )

    if not cleaned:
        return False

    try:
        return bool(
            base64.b64decode(
                cleaned,
                validate=True,
            )
        )
    except Exception:
        return False


def _positive_setting_int(
    name: str,
    *,
    fallback: int,
) -> int:
    try:
        value = int(
            getattr(
                settings,
                name,
                fallback,
            )
        )
    except (TypeError, ValueError):
        return fallback

    return value if value > 0 else fallback