#
#  apps/accounts/services/conversation_encryption_state.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-28.
#  Last Update by Hossein Sakkaki on 2026-07-28.
#


from dataclasses import dataclass

from apps.accounts.constants.conversation_encryption import (
    CONVERSATION_ENCRYPTION_BACKUP_AVAILABLE,
    CONVERSATION_ENCRYPTION_INITIALIZED_WITHOUT_BACKUP,
    CONVERSATION_ENCRYPTION_NEVER_INITIALIZED,
    CONVERSATION_ENCRYPTION_RECOVERY_METADATA_ONLY,
)
from apps.accounts.models.devices import (
    UserDeviceKey,
    UserDeviceKeyBackup,
    UserSecurityProfile,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationEncryptionState:
    state: str

    has_registered_key: bool
    has_active_registered_key: bool
    has_backup: bool
    has_passphrase: bool

    registered_device_count: int
    active_registered_device_count: int
    backup_count: int

    can_silently_provision: bool

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "has_registered_key": (
                self.has_registered_key
            ),
            "has_active_registered_key": (
                self.has_active_registered_key
            ),
            "has_backup": self.has_backup,
            "has_passphrase": self.has_passphrase,
            "registered_device_count": (
                self.registered_device_count
            ),
            "active_registered_device_count": (
                self.active_registered_device_count
            ),
            "backup_count": self.backup_count,
            "can_silently_provision": (
                self.can_silently_provision
            ),
        }


def resolve_conversation_encryption_state(
    *,
    user,
) -> ConversationEncryptionState:
    """
    Resolve the authoritative account-level encryption state.

    Any historical device key counts as prior initialization.
    Silent provisioning is allowed only when no encryption
    identity, backup, or recovery metadata exists.
    """

    registered_device_count = (
        UserDeviceKey.objects
        .filter(
            user=user,
        )
        .count()
    )

    active_registered_device_count = (
        UserDeviceKey.objects
        .filter(
            user=user,
            is_active=True,
        )
        .count()
    )

    backup_count = (
        UserDeviceKeyBackup.objects
        .filter(
            user=user,
        )
        .count()
    )

    security_profile = (
        UserSecurityProfile.objects
        .filter(
            user=user,
        )
        .only(
            "has_passphrase",
        )
        .first()
    )

    has_registered_key = (
        registered_device_count > 0
    )

    has_active_registered_key = (
        active_registered_device_count > 0
    )

    has_backup = backup_count > 0

    has_passphrase = bool(
        security_profile
        and security_profile.has_passphrase
    )

    state = _derive_state(
        has_registered_key=has_registered_key,
        has_backup=has_backup,
        has_passphrase=has_passphrase,
    )

    can_silently_provision = (
        state
        == CONVERSATION_ENCRYPTION_NEVER_INITIALIZED
    )

    return ConversationEncryptionState(
        state=state,
        has_registered_key=has_registered_key,
        has_active_registered_key=(
            has_active_registered_key
        ),
        has_backup=has_backup,
        has_passphrase=has_passphrase,
        registered_device_count=(
            registered_device_count
        ),
        active_registered_device_count=(
            active_registered_device_count
        ),
        backup_count=backup_count,
        can_silently_provision=(
            can_silently_provision
        ),
    )


def _derive_state(
    *,
    has_registered_key: bool,
    has_backup: bool,
    has_passphrase: bool,
) -> str:
    """
    Derive a fail-closed encryption state.
    """

    if has_backup:
        return (
            CONVERSATION_ENCRYPTION_BACKUP_AVAILABLE
        )

    if has_registered_key:
        return (
            CONVERSATION_ENCRYPTION_INITIALIZED_WITHOUT_BACKUP
        )

    if has_passphrase:
        return (
            CONVERSATION_ENCRYPTION_RECOVERY_METADATA_ONLY
        )

    return (
        CONVERSATION_ENCRYPTION_NEVER_INITIALIZED
    )