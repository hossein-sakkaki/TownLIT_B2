#
#  apps/accounts/account_deletion/handlers/conversation.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-04.
#  Last Update by Hossein Sakkaki on 2026-08-04.
#

import logging

from apps.accounts.account_deletion.context import (
    AccountDeletionContext,
)
from apps.accounts.account_deletion.registry import (
    account_deletion_registry,
)
from apps.accounts.models.devices import (
    UserDeviceKey,
    UserDeviceKeyBackup,
    UserSecurityProfile,
)
from apps.conversation.models import (
    Dialogue,
    DialogueParticipant,
    DialoguePin,
    Message,
    MessagePin,
    MessageReaction,
    UserDialogueMarker,
)


logger = logging.getLogger(__name__)


def _delete_message_file(
    message: Message,
    field_name: str,
) -> None:
    field = getattr(
        message,
        field_name,
        None,
    )

    if not field:
        return

    try:
        field.delete(
            save=False,
        )
    except Exception:
        logger.exception(
            "Unable to delete message asset "
            "message_id=%s field=%s",
            message.id,
            field_name,
        )


@account_deletion_registry.register(
    key="conversation",
    order=300,
)
def purge_conversation_data(
    context: AccountDeletionContext,
) -> None:
    """
    Remove keys, memberships and messages owned by the user.
    """
    user = context.user

    UserDeviceKeyBackup.objects.filter(
        user=user,
    ).delete()

    UserDeviceKey.objects.filter(
        user=user,
    ).delete()

    UserSecurityProfile.objects.filter(
        user=user,
    ).delete()

    MessageReaction.objects.filter(
        user=user,
    ).delete()

    MessagePin.objects.filter(
        pinned_by=user,
    ).delete()

    DialoguePin.objects.filter(
        user=user,
    ).delete()

    UserDialogueMarker.objects.filter(
        user=user,
    ).delete()

    DialogueParticipant.objects.filter(
        user=user,
    ).delete()

    dialogues = Dialogue.objects.filter(
        participants=user,
    )

    for dialogue in dialogues.iterator():
        dialogue.participants.remove(
            user
        )

        dialogue.deleted_by_users.remove(
            user
        )

    for message in Message.objects.filter(
        seen_by_users=user,
    ).iterator():
        message.seen_by_users.remove(
            user
        )

    for message in Message.objects.filter(
        deleted_by_users=user,
    ).iterator():
        message.deleted_by_users.remove(
            user
        )

    owned_messages = Message.objects.filter(
        sender=user,
    ).select_related(
        "dialogue",
    )

    affected_dialogue_ids = set()

    for message in owned_messages.iterator(
        chunk_size=200,
    ):
        affected_dialogue_ids.add(
            message.dialogue_id
        )

        _delete_message_file(
            message,
            "image",
        )
        _delete_message_file(
            message,
            "video",
        )
        _delete_message_file(
            message,
            "file",
        )
        _delete_message_file(
            message,
            "audio",
        )

        message.delete()

    for dialogue in Dialogue.objects.filter(
        id__in=affected_dialogue_ids,
    ).iterator():
        dialogue.refresh_last_message_cache()

        if (
            not dialogue.participants.exists()
            and not dialogue.messages.exists()
        ):
            dialogue.delete()