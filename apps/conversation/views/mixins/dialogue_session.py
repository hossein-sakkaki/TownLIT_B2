# apps/conversation/views/mixins/dialogue_session.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import asyncio
from datetime import datetime
import logging

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timesince import timesince
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models.devices import UserDeviceKey
from apps.conversation.models import Dialogue
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextPolicy,
)
from apps.conversation.serializers import DialogueSerializer
from apps.conversation.services.boundary_access import (
    can_create_private_dialogue,
    conversation_boundary_error_payload,
)
from apps.conversation.services.dialogue_lifecycle import create_or_get_private_dialogue
from apps.conversation.services.read_delivery import build_unread_count_snapshot_payload
from apps.core.security.decorators import require_litshield_access
from apps.core.websocket.services.redis_online_manager import (
    get_last_seen,
    get_online_status_for_users,
)

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


class DialogueSessionActionsMixin:
    @action(detail=False, methods=["post"], url_path="enter-chat")
    @require_litshield_access("conversation")
    def enter_chat(self, request):
        user = request.user
        device_id = request.data.get("device_id")
        # reuse same ordering as list(): DRY + consistent order
        dialogues = self._with_last_activity(self._base_qs())
        serializer = DialogueSerializer(
            dialogues,
            many=True,
            context={"request": request, "device_id": device_id}
        )
        return Response({"dialogues": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="keys", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def get_dialogue_keys(self, request, slug=None):
        dialogue = self.get_object()
        user = request.user
        if not dialogue.participants.filter(id=user.id).exists():
            return Response({"error": "Forbidden"}, status=403)
        full = request.query_params.get("full", "").lower() in ("1", "true", "yes")
        participant_ids = list(
            dialogue.participants.values_list("id", flat=True)
        )
        if not participant_ids:
            return Response(
                {"error": "No dialogue participants found."},
                status=status.HTTP_404_NOT_FOUND
            )
        qs_verified = (
            UserDeviceKey.objects
            .filter(
                user_id__in=participant_ids,
                is_active=True,
                is_verified=True,
            )
            .only("device_id", "public_key", "user_id")
            .order_by("user_id", "-last_used", "device_id")
        )
        qs_unverified = (
            UserDeviceKey.objects
            .filter(
                user_id__in=participant_ids,
                is_active=True,
                is_verified=False,
            )
            .only("device_id", "public_key", "user_id")
            .order_by("user_id", "-last_used", "device_id")
        )
        def serialize_key(key):
            return {
                "device_id": key.device_id,
                "public_key": key.public_key,
            }
        if full:
            return Response(
                {
                    "verified": [serialize_key(k) for k in qs_verified],
                    "unverified": [serialize_key(k) for k in qs_unverified],
                },
                status=status.HTTP_200_OK
            )
        return Response(
            [serialize_key(k) for k in qs_verified],
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], url_path='create-dialogue', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def create_dialogue(self, request):
        recipient_id = request.data.get('recipient_id')
        check_only = request.data.get('check_only', False)
        if not recipient_id:
            return Response(
                {'error': 'Recipient ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        recipient = get_object_or_404(CustomUser, id=recipient_id)
        boundary_check = can_create_private_dialogue(
            acting_user=request.user,
            recipient=recipient,
        )
        if not boundary_check.allowed:
            return Response(
                conversation_boundary_error_payload(
                    message=boundary_check.message,
                    code=boundary_check.code,
                ),
                status=status.HTTP_403_FORBIDDEN,
            )
        result = create_or_get_private_dialogue(
            acting_user=request.user,
            recipient=recipient,
            check_only=check_only,
        )
        if not result.get("ok"):
            if result["status"] == 204:
                return Response(
                    {'message': result["message"]},
                    status=status.HTTP_204_NO_CONTENT
                )
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        dialogue = payload["dialogue"]
        device_id = request.data.get("device_id")
        serializer = DialogueSerializer(
            dialogue,
            context={"request": request, "device_id": device_id},
        )
        return Response(
            {
                'dialogue': serializer.data,
                'message': payload["message"],
            },
            status=status.HTTP_201_CREATED if payload["created"] else status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='last-seen', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def get_last_seen_view(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug)
        if ConversationContextPolicy.resolve(dialogue).is_organization:
            access = ConversationAccessPolicy.can_view(
                dialogue=dialogue,
                user=request.user,
            )
            if not access.allowed:
                return Response(
                    {"error": access.message, "code": access.code},
                    status=status.HTTP_403_FORBIDDEN,
                )
        if dialogue.is_group:
            return Response({
                'note': 'Last seen is not applicable to group chats.',
                'user_id': None,
                'is_online': None,
                'last_seen': None,
                'last_seen_display': None
            }, status=status.HTTP_200_OK)
        if request.user not in dialogue.participants.all():
            return Response({'error': 'You are not a participant of this dialogue.'}, status=status.HTTP_403_FORBIDDEN)
        participant = dialogue.participants.exclude(id=request.user.id).first()
        if not participant:
            return Response({'error': 'No other participant found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            online_status = asyncio.run(get_online_status_for_users([participant.id]))
        except Exception as e:
            return Response({'error': 'Failed to check online status.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if online_status.get(participant.id):
            return Response({
                'user_id': participant.id,
                'is_online': True,
                'last_seen': None,
                'last_seen_display': "Online"
            })
        try:
            last_seen_ts = asyncio.run(get_last_seen(participant.id))
            if last_seen_ts:
                # ✅ datetime آگاه به منطقه
                last_seen_dt = datetime.fromtimestamp(last_seen_ts, tz=timezone.utc)
                return Response({
                    'user_id': participant.id,
                    'is_online': False,
                    'last_seen': last_seen_dt.isoformat(),
                    'last_seen_epoch': last_seen_ts,
                    'last_seen_display': timesince(
                        last_seen_dt,
                        timezone.now()
                    ),
                })
        except Exception as e:
            logger.error("❌ Error getting last seen:", e)
        return Response({
            'user_id': participant.id,
            'is_online': False,
            'last_seen': None,
            'last_seen_display': "Unknown"
        })

    @action(detail=False, methods=["get"], url_path="unread-counts", permission_classes=[IsAuthenticated])
    def get_unread_counts(self, request):
        user = request.user
        dialogues = (
            Dialogue.objects
            .filter(participants=user)
            .exclude(deleted_by_users=user)
            .select_related("organization_context__organization")
        )
        results = []
        for dialogue in dialogues:
            if ConversationContextPolicy.resolve(dialogue).is_organization:
                access = ConversationAccessPolicy.can_view(
                    dialogue=dialogue,
                    user=user,
                )
                if not access.allowed:
                    continue
            results.append({
                "dialogue_slug": dialogue.slug,
                "unread_count": dialogue.unread_messages_for_user(user).count(),
            })
        return Response(build_unread_count_snapshot_payload(results))
