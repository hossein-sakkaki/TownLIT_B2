# apps/conversation/views/mixins/message_state.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.conversation.models import Dialogue, Message
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.services.event_contracts import (
    build_delivery_event_data,
    build_dm_edit_message_data,
    build_group_edit_message_data,
    build_hard_delete_event_data,
)
from apps.conversation.services.message_mutations import (
    build_message_soft_deleted_realtime_payload,
    edit_message_content,
    hard_delete_message_for_user,
    soft_delete_message_for_user,
)
from apps.conversation.services.read_delivery import (
    build_mark_as_read_realtime_payload,
    mark_dialogue_read_for_user,
    mark_message_delivered_for_user,
)
from apps.conversation.services.message_visibility import (
    is_members_community,
    visible_message_ids_for_user,
    visible_participant_ids_for_message,
)
from apps.conversation.services.realtime_dispatch import conv_group_send

logger = logging.getLogger(__name__)


def _external_organization_direct_seen_payload(*, message, user):
    """Return aggregate read receipt without exposing Organization operators."""
    context = ConversationContextPolicy.resolve(message.dialogue)
    if context.kind != ConversationContextKind.ORGANIZATION_DIRECT:
        return None

    participant_user_id = context.organization_context.participant_user_id
    if (
        getattr(user, "id", None) != participant_user_id
        or message.sender_id != participant_user_id
    ):
        return None

    return {
        "seen_by_organization": (
            message.seen_by_users
            .exclude(id=participant_user_id)
            .exists()
        )
    }


class MessageStateActionsMixin:
    @action(detail=True, methods=['post'], url_path='edit-message', permission_classes=[IsAuthenticated])
    def edit_message(self, request, pk=None):
        try:
            logger.info(">> [EDIT] Starting edit_message for pk=%s user=%s", pk, request.user)
            message = get_object_or_404(
                Message.objects.select_related("dialogue", "sender"),
                pk=pk
            )
            dialogue = message.dialogue
            context = ConversationContextPolicy.resolve(dialogue)
            if context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
                return Response(
                    {
                        "error": (
                            "Message editing is not available for "
                            "Organization Direct conversations."
                        ),
                        "code": "ORGANIZATION_DIRECT_FEATURE_NOT_AVAILABLE",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            is_group = bool(dialogue.is_group)
            # Verify device PoP
            header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
            if not header_device:
                return Response(
                    {"error": "X-Device-ID header is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not is_sender_device_verified(
                request.user,
                header_device,
                dialogue_is_group=is_group,
            ):
                return Response(
                    {
                        "error": "Sender device is not verified.",
                        "code": "SENDER_DEVICE_UNVERIFIED",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            result = edit_message_content(
                message_id=message.id,
                acting_user=request.user,
                new_content=(request.data.get("content") or "").strip(),
                encrypted_contents=request.data.get("encrypted_contents", []),
            )
            if not result.get("ok"):
                return Response(
                    {"error": result["message"], "code": result["code"]},
                    status=result["status"],
                )
            payload = result["payload"]
            # Community edit events must respect joined-at history.
            if payload["is_group"]:
                edit_data = build_group_edit_message_data(payload=payload)
                if is_members_community(dialogue):
                    for uid in visible_participant_ids_for_message(
                        message=message,
                    ):
                        conv_group_send(
                            f"user_{uid}",
                            "edit_message",
                            edit_data,
                        )
                else:
                    conv_group_send(
                        f"dialogue_{payload['dialogue_slug']}",
                        "edit_message",
                        edit_data,
                    )
            else:
                # DM edit -> broadcast per-device canonical payload
                participants = list(dialogue.participants.all())
                participant_ids = [p.id for p in participants]
                user_device_map = {}
                for uid in participant_ids:
                    user_device_map[uid] = set(
                        UserDeviceKey.objects.filter(user_id=uid, is_active=True)
                        .values_list("device_id", flat=True)
                    )
                for enc in payload.get("encrypted_contents", []):
                    device_id = enc["device_id"]
                    encrypted_blob = enc["encrypted_content"]
                    edit_data = build_dm_edit_message_data(
                        payload=payload,
                        device_id=device_id,
                        encrypted_content=encrypted_blob,
                    )
                    for participant in participants:
                        participant_device_ids = user_device_map.get(participant.id, set())
                        if device_id not in participant_device_ids:
                            continue
                        conv_group_send(
                            f"user_device_{participant.id}_{device_id}",
                            "edit_message",
                            edit_data,
                        )
            return Response(
                {"message": "Message edited successfully."},
                status=status.HTTP_200_OK
            )
        except APIException:
            raise
        except Exception as e:
            logger.exception(
                "‼️ ERROR DURING edit_message(): %s",
                e,
            )
            return Response(
                {
                    "error": "Internal server error",
                    "details": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'], url_path='mark-as-delivered')
    def mark_as_delivered(self, request):
        result = mark_message_delivered_for_user(
            request.data.get("dialogue_slug"),
            request.data.get("message_id"),
            request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        realtime_data = build_delivery_event_data(
            dialogue_slug=payload["dialogue_slug"],
            message_id=payload["message_id"],
            user_id=payload["user_id"],
            is_delivered=payload["is_delivered"],
        )
        conv_group_send(
            f"user_{payload['sender_id']}",
            "mark_as_delivered",
            realtime_data,
        )
        dialogue = Dialogue.objects.get(slug=payload["dialogue_slug"])
        if is_members_community(dialogue):
            message = Message.objects.get(
                id=payload["message_id"],
                dialogue=dialogue,
            )
            for uid in visible_participant_ids_for_message(
                message=message,
            ):
                if uid == payload["sender_id"]:
                    continue
                conv_group_send(
                    f"user_{uid}",
                    "mark_as_delivered",
                    realtime_data,
                )
        else:
            conv_group_send(
                f"dialogue_{payload['dialogue_slug']}",
                "mark_as_delivered",
                realtime_data,
            )
        return Response(
            {"message": "Message marked as delivered."},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], url_path='mark-as-read')
    def mark_as_read(self, request):
        dialogue_slug = request.data.get("dialogue_slug")
        user = request.user
        result = mark_dialogue_read_for_user(dialogue_slug, user)
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        dialogue = Dialogue.objects.get(
            slug=payload["dialogue_slug"],
            participants=user,
        )
        participant_ids = list(
            dialogue.participants.exclude(id=user.id)
            .values_list("id", flat=True)
        )
        if is_members_community(dialogue):
            participants = {
                participant.id: participant
                for participant in dialogue.participants
                .filter(id__in=participant_ids)
                .only("id")
            }
            for uid in participant_ids:
                participant = participants.get(uid)
                if participant is None:
                    continue
                visible_ids = visible_message_ids_for_user(
                    dialogue=dialogue,
                    user=participant,
                    message_ids=payload.get("read_messages", []),
                )
                if not visible_ids:
                    continue
                recipient_payload = {
                    **payload,
                    "read_messages": visible_ids,
                }
                conv_group_send(
                    f"user_{uid}",
                    "mark_as_read",
                    build_mark_as_read_realtime_payload(recipient_payload),
                )
        else:
            realtime_data = build_mark_as_read_realtime_payload(payload)
            for uid in participant_ids:
                conv_group_send(
                    f"user_{uid}",
                    "mark_as_read",
                    realtime_data,
                )
            conv_group_send(
                f"dialogue_{payload['dialogue_slug']}",
                "mark_as_read",
                realtime_data,
            )
        return Response(
            {
                'message': 'Messages marked as read.',
                'read_messages': payload.get("read_messages", []),
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='seen-by', permission_classes=[IsAuthenticated])
    def seen_by(self, request, pk=None):
        message = get_object_or_404(
            Message.objects
            .select_related("dialogue", "sender")
            .prefetch_related("seen_by_users"),
            pk=pk,
        )
        user = request.user
        dialogue = message.dialogue
        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not (
            dialogue.visible_messages_for_user(user)
            .filter(id=message.id)
            .exists()
        ):
            return Response(
                {"error": "Message not found.", "code": "MESSAGE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        external_org_seen = _external_organization_direct_seen_payload(
            message=message,
            user=user,
        )
        if external_org_seen is not None:
            return Response(
                external_org_seen,
                status=status.HTTP_200_OK,
            )

        is_sender = message.sender_id == user.id
        if dialogue.is_group:
            # Group policy:
            # - Founder / elder can inspect seen details.
            # - Message sender can inspect seen details for their own message.
            can_view_seen_by = (
                is_sender
                or dialogue.is_founder(user)
                or dialogue.is_elder(user)
            )
        else:
            # Private E2EE policy:
            # - Only the sender can inspect seen details for their own outgoing message.
            can_view_seen_by = is_sender
        if not can_view_seen_by:
            return Response(
                {"error": "Permission denied.", "code": "SEEN_BY_PERMISSION_DENIED"},
                status=status.HTTP_403_FORBIDDEN,
            )
        seen_qs = (
            message.seen_by_users
            .exclude(pk=message.sender_id)
            .exclude(pk=user.pk)
            .select_related("label", "member_profile")
            .order_by("username")
        )
        serializer = SimpleCustomUserSerializer(
            seen_qs,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='soft-delete', permission_classes=[IsAuthenticated])
    def soft_delete_message(self, request, pk=None):
        result = soft_delete_message_for_user(
            message_id=pk,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        realtime_data = build_message_soft_deleted_realtime_payload(payload)
        conv_group_send(
            f"user_{request.user.id}",
            "message_soft_deleted",
            realtime_data,
        )
        conv_group_send(
            f"user_{request.user.id}",
            "trigger_unread_count_update",
            {},
        )
        return Response(
            {'message': 'Message soft deleted successfully.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='hard-delete', permission_classes=[IsAuthenticated])
    def hard_delete_message(self, request, pk=None):
        result = hard_delete_message_for_user(
            message_id=pk,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"]
            )
        payload = result["payload"]
        realtime_data = build_hard_delete_event_data(
            dialogue_slug=payload["dialogue_slug"],
            message_id=payload["message_id"],
        )
        for uid in payload["participant_ids"]:
            conv_group_send(
                f"user_{uid}",
                "message_hard_deleted",
                realtime_data,
            )
            conv_group_send(
                f"user_{uid}",
                "trigger_unread_count_update",
                {},
            )
        return Response(
            {"message": "Message permanently deleted."},
            status=status.HTTP_200_OK
        )
