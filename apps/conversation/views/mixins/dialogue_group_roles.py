# apps/conversation/views/mixins/dialogue_group_roles.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.models import Dialogue
from apps.conversation.services.event_contracts import build_founder_transferred_event_data, build_group_left_event_data, build_group_removed_event_data
from apps.conversation.services.group_domain import (
    build_group_role_changed_system_text,
    demote_group_elder_to_participant,
    leave_group_as_participant,
    promote_group_participant_to_elder,
    resign_group_elder_role,
    transfer_group_founder,
)
from apps.conversation.services.realtime_dispatch import conv_group_send
from apps.core.security.decorators import require_litshield_access
from django.shortcuts import get_object_or_404

from ..helpers import _broadcast_group_updated, _dialogue_payload_for_realtime, send_system_message


class DialogueGroupRoleActionsMixin:
    @action(detail=True, methods=['post'], url_path='promote-to-elder', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def promote_to_elder(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID is required.'}, status=400)
        result = promote_group_participant_to_elder(
            dialogue=dialogue,
            acting_user=request.user,
            target_user_id=user_id,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        participant_user = result["payload"]["participant"]
        system_event, system_text = build_group_role_changed_system_text(
            "promoted_to_elder",
            participant_user.username,
        )
        # No special targeted realtime event here.
        # System message is the canonical chat-stream signal.
        send_system_message(dialogue, request.user, system_event, system_text)
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="role_promoted_to_elder",
            actor_user=request.user,
            target_user=participant_user,
        )
        return Response({'message': 'User promoted to Elder.'}, status=200)

    @action(detail=True, methods=['post'], url_path='demote-to-participant', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def demote_to_participant(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'User ID is required.'}, status=400)
        result = demote_group_elder_to_participant(
            dialogue=dialogue,
            acting_user=request.user,
            target_user_id=user_id,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        participant_user = result["payload"]["participant"]
        system_event, system_text = build_group_role_changed_system_text(
            "demoted_to_participant",
            participant_user.username,
        )
        send_system_message(dialogue, request.user, system_event, system_text)
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="role_demoted_to_participant",
            actor_user=request.user,
            target_user=participant_user,
        )
        return Response({'message': 'User demoted to Participant.'}, status=200)

    @action(detail=True, methods=['post'], url_path='resign-elder-role', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def resign_elder_role(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        result = resign_group_elder_role(
            dialogue=dialogue,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        system_event, system_text = build_group_role_changed_system_text(
            "resigned_from_elder",
            request.user.username,
        )
        send_system_message(dialogue, request.user, system_event, system_text)
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="elder_resigned",
            actor_user=request.user,
            target_user=request.user,
        )
        return Response({'message': 'You stepped down as an Elder.'}, status=200)

    @action(detail=True, methods=['post'], url_path='leave-group', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def leave_group(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        result = leave_group_as_participant(
            dialogue=dialogue,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        serialized_user = SimpleCustomUserSerializer(
            request.user,
            context={"request": request}
        ).data
        realtime_data = build_group_left_event_data(
            user=serialized_user,
            dialogue_slug=dialogue.slug,
        )
        # Notify all current devices of the leaving user to remove this group locally
        # and discard stale dialogue channel membership.
        dialogue_payload = _dialogue_payload_for_realtime(dialogue, request)
        conv_group_send(
            f"user_{request.user.id}",
            "group_removed",
            build_group_removed_event_data(dialogue=dialogue_payload),
        )
        # 1) Targeted realtime event first
        for participant in dialogue.participants.exclude(id=request.user.id):
            conv_group_send(
                f"user_{participant.id}",
                "group_left",
                realtime_data,
            )
        # 2) Then system message to dialogue stream
        send_system_message(
            dialogue,
            request.user,
            "left",
            f"{request.user.username} left the group.",
        )
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="member_left",
            actor_user=request.user,
            target_user=request.user,
        )
        return Response(
            {'message': 'You left the group and your chat was removed from the list.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='transfer-founder', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def transfer_founder(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        new_founder_id = request.data.get('user_id')
        if not new_founder_id:
            return Response({'error': 'New founder user_id is required.'}, status=400)
        result = transfer_group_founder(
            dialogue=dialogue,
            acting_user=request.user,
            new_founder_user_id=new_founder_id,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        new_founder = payload["new_founder"]
        realtime_data = build_founder_transferred_event_data(
            dialogue_slug=dialogue.slug,
            new_founder_id=new_founder.id,
        )
        # 1) Targeted realtime event first
        for user in dialogue.participants.all():
            conv_group_send(
                f"user_{user.id}",
                "founder_transferred",
                realtime_data,
            )
        # 2) Then system message
        send_system_message(
            dialogue,
            request.user,
            "founder_transferred",
            f"Founder role transferred to {new_founder.username}.",
        )
        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="founder_transferred",
            actor_user=request.user,
            target_user=new_founder,
        )
        return Response(
            {'message': 'Founder role transferred successfully.'},
            status=200
        )
