# apps/conversation/views/helpers.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import base64
import json

from rest_framework.renderers import JSONRenderer

from apps.conversation.models import Message
from apps.conversation.serializers import DialogueSerializer
from apps.conversation.services.event_contracts import (
    build_group_updated_event_data,
    build_system_chat_message_data,
)
from apps.conversation.services.realtime_dispatch import (
    conv_group_send,
    conversation_dialogue_group_name,
)


def _dialogue_payload_for_realtime(dialogue, request):
    """
    Serialize dialogue once for realtime UI sync.
    Note:
    my_role is request-user scoped. For shared group_updated events, clients should
    treat this snapshot as display-oriented and refresh participants/roles when needed.
    """
    serializer = DialogueSerializer(dialogue, context={"request": request})
    json_data = JSONRenderer().render(serializer.data)
    return json.loads(json_data)


def _broadcast_group_updated(
    *,
    dialogue,
    request,
    reason: str,
    actor_user=None,
    target_user=None,
):
    """
    Broadcast a generic group_updated event to active group sockets.
    System messages update the chat stream.
    group_updated updates header/list/avatar/roles/member count.
    """
    dialogue_payload = _dialogue_payload_for_realtime(dialogue, request)
    data = build_group_updated_event_data(
        dialogue_slug=dialogue.slug,
        reason=reason,
        dialogue=dialogue_payload,
        actor_id=getattr(actor_user, "id", None),
        target_user_id=getattr(target_user, "id", None),
    )
    conv_group_send(
        conversation_dialogue_group_name(dialogue.slug),
        "group_updated",
        data,
    )


def send_system_message(dialogue, sender, system_event, content):
    plain_text = (content or "").strip()
    if not plain_text:
        return None
    # Store plaintext in current DB format: base64 text bytes.
    base64_str = base64.b64encode(
        plain_text.encode("utf-8")
    ).decode("utf-8")
    content_bytes = base64_str.encode("utf-8")
    system_message = Message.objects.create(
        dialogue=dialogue,
        sender=sender,
        content_encrypted=content_bytes,
        is_system=True,
        system_event=system_event,
    )
    # Keep system message visible in realtime chat stream,
    # but do not overwrite global non-system last_message cache.
    conv_group_send(
        conversation_dialogue_group_name(dialogue.slug),
        "chat_message",
        build_system_chat_message_data(
            dialogue=dialogue,
            system_message=system_message,
            sender=sender,
            plain_text=plain_text,
            system_event=system_event,
        ),
    )
    return system_message
