# apps/conversation/views/mixins/message_pins.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.serializers import MessagePinSerializer
from apps.conversation.services.event_contracts import (
    build_message_pin_event_data,
    build_message_unpin_event_data,
)
from apps.conversation.services.message_visibility import (
    visible_participant_ids_for_message,
)
from apps.conversation.services.message_pins import (
    pin_message_for_dialogue,
    unpin_message_for_dialogue,
)
from apps.conversation.services.messenger_notification_adapter import notify_message_pinned
from apps.conversation.services.realtime_dispatch import (
    conv_group_send,
    conversation_user_group_name,
)


class MessagePinActionsMixin:
    @action(detail=True, methods=["post"], url_path="pin-message", permission_classes=[IsAuthenticated])
    def pin_message(self, request, pk=None):
        pin_duration = (request.data.get("pin_duration") or "none").strip()
        reminders_enabled = bool(request.data.get("reminders_enabled", False))
        result = pin_message_for_dialogue(
            message_id=pk,
            acting_user=request.user,
            pin_duration=pin_duration,
            reminders_enabled=reminders_enabled,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        pin = result["payload"]["pin"]
        dialogue = result["payload"]["dialogue"]
        realtime_data = build_message_pin_event_data(pin=pin)
        # Community history boundaries also apply to realtime pin events.
        for user_id in visible_participant_ids_for_message(message=pin.message):
            conv_group_send(
                conversation_user_group_name(user_id),
                "message_pinned",
                realtime_data,
            )
        # Push-only Messenger notification for group members.
        # The adapter intentionally skips private chats and skips the actor.
        notify_message_pinned(
            pin=pin,
            actor=request.user,
        )
        return Response(
            {
                "message": result["payload"]["result_message"],
                "pin": MessagePinSerializer(
                    pin,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="unpin-message", permission_classes=[IsAuthenticated])
    def unpin_message(self, request, pk=None):
        result = unpin_message_for_dialogue(
            message_id=pk,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        dialogue = result["payload"]["dialogue"]
        message = result["payload"]["message"]
        realtime_data = build_message_unpin_event_data(
            dialogue_slug=dialogue.slug,
            message_id=message.id,
        )
        for user_id in visible_participant_ids_for_message(message=message):
            conv_group_send(
                f"user_{user_id}",
                "message_unpinned",
                realtime_data,
            )
        return Response(
            {
                "message": result["payload"]["result_message"],
            },
            status=status.HTTP_200_OK,
        )
