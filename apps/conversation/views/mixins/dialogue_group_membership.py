# apps/conversation/views/mixins/dialogue_group_membership.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import json

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apps.conversation.models import Dialogue, DialogueParticipant
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextPolicy,
)
from apps.conversation.serializers import DialogueParticipantSerializer, DialogueSerializer
from apps.conversation.services.boundary_access import can_add_user_to_group
from apps.conversation.services.event_contracts import build_group_added_event_data, build_group_removed_event_data
from apps.conversation.services.group_domain import add_group_participant, remove_group_participant
from apps.conversation.services.messenger_notification_adapter import notify_group_created_or_user_added
from apps.conversation.services.realtime_dispatch import conv_group_send, conversation_user_group_name
from apps.core.security.decorators import require_litshield_access

from ..helpers import _broadcast_group_updated, send_system_message

CustomUser = get_user_model()


class DialogueGroupMembershipActionsMixin:
    @action(detail=True, methods=['post'], url_path='add-participant', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def add_participant(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        participant_id = request.data.get('participant_id')
        if not participant_id:
            return Response(
                {'error': 'Participant ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        participant = get_object_or_404(CustomUser, pk=participant_id)
        boundary_check = can_add_user_to_group(
            dialogue=dialogue,
            target_user=participant,
        )
        if not boundary_check.allowed:
            return Response(
                {
                    "error": boundary_check.message,
                    "code": boundary_check.code,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        result = add_group_participant(
            dialogue=dialogue,
            acting_user=request.user,
            target_user=participant,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        # Refresh dialogue from DB after membership mutation.
        dialogue.refresh_from_db()
        serializer = DialogueSerializer(dialogue, context={"request": request})
        json_data = JSONRenderer().render(serializer.data)
        parsed_data = json.loads(json_data)
        parsed_data["my_role"] = "participant"
        # 1) Targeted conversation realtime event.
        conv_group_send(
            conversation_user_group_name(participant.id),
            "group_added",
            build_group_added_event_data(dialogue=parsed_data),
        )
        # 2) System chat-stream message.
        send_system_message(
            dialogue,
            request.user,
            "joined",
            f"{participant.username} joined the group.",
        )
        # 3) Shared group metadata refresh.
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="member_added",
            actor_user=request.user,
            target_user=participant,
        )
        # 4) Push-only Messenger notification.
        # This does not create a Notification row, WS notification, or email.
        notify_group_created_or_user_added(
            dialogue=dialogue,
            actor=request.user,
            recipients=[participant],
        )
        return Response(
            {'message': f'{participant.username} added to the group.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='remove-participant', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def remove_participant(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        participant_id = request.data.get('participant_id')
        if not participant_id:
            return Response(
                {'error': 'Participant ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        participant = get_object_or_404(CustomUser, pk=participant_id)
        result = remove_group_participant(
            dialogue=dialogue,
            acting_user=request.user,
            target_user=participant,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        serializer = DialogueSerializer(dialogue, context={"request": request})
        json_data = JSONRenderer().render(serializer.data)
        parsed_data = json.loads(json_data)
        # 1) Targeted realtime event
        conv_group_send(
            f"user_{participant.id}",
            "group_removed",
            build_group_removed_event_data(dialogue=parsed_data),
        )
        # 2) System message after targeted event
        send_system_message(
            dialogue,
            request.user,
            "removed",
            f"{participant.username} was removed from the group.",
        )
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="member_removed",
            actor_user=request.user,
            target_user=participant,
        )
        return Response(
            {'message': f'{participant.username} removed from the group.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='participants', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def get_group_participants(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        context = ConversationContextPolicy.resolve(dialogue)
        if context.is_organization:
            access = ConversationAccessPolicy.can_view(
                dialogue=dialogue,
                user=request.user,
            )
            if not access.allowed:
                return Response(
                    {"error": access.message, "code": access.code},
                    status=status.HTTP_403_FORBIDDEN,
                )
        participants = DialogueParticipant.objects.filter(dialogue=dialogue).select_related('user')
        serializer = DialogueParticipantSerializer(
            participants,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
