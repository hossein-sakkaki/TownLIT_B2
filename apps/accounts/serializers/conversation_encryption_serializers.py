#
#  apps/accounts/serializers/conversation_encryption_serializers.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-28.
#  Last Update by Hossein Sakkaki on 2026-07-28.
#


from rest_framework import serializers

from apps.accounts.constants.conversation_encryption import (
    CONVERSATION_ENCRYPTION_STATES,
)


class ConversationEncryptionStateSerializer(
    serializers.Serializer
):
    state = serializers.ChoiceField(
        choices=sorted(
            CONVERSATION_ENCRYPTION_STATES
        ),
    )

    has_registered_key = serializers.BooleanField()

    has_active_registered_key = (
        serializers.BooleanField()
    )

    has_backup = serializers.BooleanField()

    has_passphrase = serializers.BooleanField()

    registered_device_count = (
        serializers.IntegerField(
            min_value=0,
        )
    )

    active_registered_device_count = (
        serializers.IntegerField(
            min_value=0,
        )
    )

    backup_count = serializers.IntegerField(
        min_value=0,
    )

    can_silently_provision = (
        serializers.BooleanField()
    )