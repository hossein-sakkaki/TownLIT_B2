# apps/conversation/services/file_realtime.py

from apps.accounts.models.devices import UserDeviceKey
from apps.conversation.models import MessageEncryption
from apps.conversation.services.event_contracts import (
    build_file_message_event_data,
    build_file_upload_status_event_data,
    build_recording_status_event_data,
    build_upload_canceled_event_data,
)
from apps.conversation.services.message_reply import build_reply_preview
from apps.conversation.services.message_forward import build_forward_preview
from apps.conversation.services.message_media_descriptors import (
    build_message_media_descriptors,
)


def build_file_message_payload(message, dialogue_slug, file_type, file_url=None):
    """
    Build canonical realtime payload for file_message events.
    """
    reply_preview = build_reply_preview(
        message=message,
        acting_user=getattr(message, "sender", None),
    )
    forward_preview = build_forward_preview(message=message)

    return build_file_message_event_data(
        message=message,
        dialogue_slug=dialogue_slug,
        file_type=file_type,
        file_url=file_url,
        reply_preview=reply_preview,
        forward_preview=forward_preview,
    )
    

def get_hidden_recipient_ids_for_message(message):
    """
    Return recipients who must not receive the file event.
    """
    return set(message.deleted_by_users.values_list("id", flat=True))


def get_blocked_device_ids_for_users(user_ids):
    """
    Resolve device ids that belong to hidden recipients.
    """
    if not user_ids:
        return set()

    return set(
        UserDeviceKey.objects.filter(user_id__in=user_ids)
        .values_list("device_id", flat=True)
    )


def get_user_device_map(user_ids):
    """
    Resolve active device ids for each participant.
    """
    result = {}

    for uid in user_ids:
        result[uid] = set(
            UserDeviceKey.objects.filter(user_id=uid, is_active=True)
            .values_list("device_id", flat=True)
        )

    return result


def get_message_encryption_rows(message):
    """
    Return per-device encryption rows for this message.
    """
    return list(
        MessageEncryption.objects.filter(message=message)
        .values("device_id", "encrypted_content")
    )


def resolve_file_message_targets(message):
    """
    Resolve realtime routing plan for one file message.

    Returns:
        {
            "mode": "group_broadcast" | "dm_group_broadcast" | "dm_device_broadcast" | "skip",
            "group_name": str | None,
            "device_targets": [
                {"group_name": "...", "device_id": "..."}
            ],
        }
    """
    dialogue = message.dialogue
    dialogue_slug = dialogue.slug

    if dialogue.is_group:
        return {
            "mode": "group_broadcast",
            "group_name": f"dialogue_{dialogue_slug}",
            "device_targets": [],
        }

    hidden_recipient_ids = get_hidden_recipient_ids_for_message(message)
    blocked_device_ids = get_blocked_device_ids_for_users(hidden_recipient_ids)

    if not blocked_device_ids:
        return {
            "mode": "dm_group_broadcast",
            "group_name": f"dialogue_{dialogue_slug}",
            "device_targets": [],
        }

    if not getattr(message, "is_encrypted_file", False):
        return {
            "mode": "skip",
            "group_name": None,
            "device_targets": [],
        }

    participants = list(dialogue.participants.all())
    participant_ids = [p.id for p in participants]
    user_device_map = get_user_device_map(participant_ids)
    enc_rows = get_message_encryption_rows(message)

    device_targets = []

    for participant in participants:
        participant_device_ids = user_device_map.get(participant.id, set())
        if not participant_device_ids:
            continue

        if participant.id in hidden_recipient_ids:
            continue

        for enc in enc_rows:
            device_id = enc["device_id"]

            if device_id not in participant_device_ids:
                continue

            if device_id in blocked_device_ids:
                continue

            device_targets.append({
                "group_name": f"user_device_{participant.id}_{device_id}",
                "device_id": device_id,
            })

    return {
        "mode": "dm_device_broadcast",
        "group_name": None,
        "device_targets": device_targets,
    }


def build_file_upload_status_payload(*, dialogue_slug, sender, file_type, status, progress=None):
    """
    Build canonical realtime payload for file upload status.
    """
    return build_file_upload_status_event_data(
        dialogue_slug=dialogue_slug,
        user=sender,
        file_type=file_type,
        status=status,
        progress=progress,
    )


def build_recording_status_payload(*, dialogue_slug, sender, file_type, is_recording):
    """
    Build canonical realtime payload for recording status.
    """
    return build_recording_status_event_data(
        dialogue_slug=dialogue_slug,
        user=sender,
        file_type=file_type,
        is_recording=is_recording,
    )


def build_upload_canceled_payload(*, dialogue_slug, file_type):
    """
    Build canonical realtime payload for upload cancel events.
    """
    return build_upload_canceled_event_data(
        dialogue_slug=dialogue_slug,
        file_type=file_type,
    )