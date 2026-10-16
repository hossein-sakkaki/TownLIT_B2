# apps/conversation/views/mixins/message_reactions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import Message
from apps.conversation.policies import ConversationAccessPolicy
from apps.conversation.services.boundary_access import CONVERSATION_INTERACTION_UNAVAILABLE_CODE
from apps.conversation.services.event_contracts import build_message_reaction_toggled_event_data
from apps.conversation.services.message_visibility import (
    visible_participant_ids_for_message,
)
from apps.conversation.services.message_reactions import (
    get_message_reaction_summary_for_user,
    list_message_reactors,
    toggle_message_reaction,
)
from apps.conversation.services.messenger_notification_adapter import notify_message_reaction
from apps.conversation.services.realtime_dispatch import (
    conv_group_send,
    conversation_user_group_name,
)
from apps.core.boundaries.constants import BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE
from apps.core.boundaries.services.policy import BoundaryPolicy


class MessageReactionActionsMixin:
    @action(detail=True, methods=["post"], url_path="toggle-reaction", permission_classes=[IsAuthenticated])
    def toggle_reaction(self, request, pk=None):
        reaction_type = request.data.get("reaction_type")
        target_message = get_object_or_404(
            Message.objects.select_related("dialogue", "sender"),
            pk=pk,
        )
        dialogue = target_message.dialogue
        if not dialogue.participants.filter(id=request.user.id).exists():
            return Response(
                {
                    "error": "Access denied.",
                    "code": "DIALOGUE_ACCESS_DENIED",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=request.user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not (
            dialogue.visible_messages_for_user(request.user)
            .filter(id=target_message.id)
            .exists()
        ):
            return Response(
                {
                    "error": "Message not found.",
                    "code": "MESSAGE_NOT_VISIBLE",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        if (
            target_message.sender_id != request.user.id
            and BoundaryPolicy.has_boundary_between(request.user, target_message.sender)
        ):
            return Response(
                {
                    "error": BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
                    "code": CONVERSATION_INTERACTION_UNAVAILABLE_CODE,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        result = toggle_message_reaction(
            message_id=pk,
            acting_user=request.user,
            reaction_type=reaction_type,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        payload = result["payload"]
        message = payload["message"]
        dialogue = message.dialogue
        summary = payload["summary"]
        reaction_action = (payload.get("action") or "").strip().lower()
        normalized_reaction_type = payload.get("reaction_type") or reaction_type
        realtime_data = build_message_reaction_toggled_event_data(
            dialogue_slug=dialogue.slug,
            message_id=message.id,
            user_id=request.user.id,
            reaction_type=normalized_reaction_type,
            action=reaction_action,
            summary=summary,
        )
        # Shared state only reaches users who can see this message.
        for user_id in visible_participant_ids_for_message(message=message):
            conv_group_send(
                conversation_user_group_name(user_id),
                "message_reaction_toggled",
                realtime_data,
            )
        # Push-only Messenger notification.
        # Direct: notify the original sender.
        # Group: notify only the original sender, not every group member.
        notify_message_reaction(
            message=message,
            actor=request.user,
            reaction_type=normalized_reaction_type,
            reaction_action=reaction_action,
        )
        return Response(
            {
                "message": "Reaction updated successfully.",
                "action": reaction_action,
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="reaction-summary", permission_classes=[IsAuthenticated])
    def reaction_summary(self, request, pk=None):
        result = get_message_reaction_summary_for_user(
            message_id=pk,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        return Response(
            result["payload"]["summary"],
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="reactors", permission_classes=[IsAuthenticated])
    def reactors(self, request, pk=None):
        result = list_message_reactors(
            message_id=pk,
            acting_user=request.user,
            request=request,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        return Response(
            {
                "count": result["payload"]["count"],
                "results": result["payload"]["reactors"],
            },
            status=status.HTTP_200_OK,
        )
