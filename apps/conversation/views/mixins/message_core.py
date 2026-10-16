# apps/conversation/views/mixins/message_core.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.conversation.models import Dialogue, Message, MessageEncryption
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.serializers import MessageSerializer
from apps.conversation.services.boundary_access import private_dialogue_boundary_response_payload
from apps.conversation.services.message_creation import create_text_message
from apps.conversation.services.organization import mark_after_participant_message
from apps.conversation.services.realtime_dispatch import broadcast_group_text_message
from apps.conversation.utils import get_websocket_url


class MessageCoreActionsMixin:
    def list(self, request, dialogue_slug=None):
        """ Retrieve messages for a dialogue with pagination """
        dialogue_slug = request.query_params.get("dialogue_slug")
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 20))
        device_id = request.query_params.get("device_id", "")
        device_id = device_id.strip().lower()
        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=request.user)
        access = ConversationAccessPolicy.can_view(
            dialogue=dialogue,
            user=request.user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=status.HTTP_403_FORBIDDEN,
            )
        messages_query = dialogue.visible_messages_for_user(request.user).order_by("-timestamp")
        total_messages = messages_query.count()
        has_more = offset + limit < total_messages
        messages = messages_query[offset:offset + limit]
        is_encrypted = MessageEncryption.objects.filter(message__dialogue=dialogue).exists()
        serializer = MessageSerializer(
            messages,
            many=True,
            context={'request': request, 'device_id': device_id}
        )
        return Response({
            'is_encrypted': is_encrypted,
            'messages': serializer.data,
            'has_more': has_more
        }, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['post'],
        url_path='send-message',
        permission_classes=[IsAuthenticated],
        parser_classes=[JSONParser],
    )
    def send_message(self, request):
        user = request.user
        dialogue_slug = request.data.get("dialogue_slug")
        is_encrypted = bool(request.data.get("is_encrypted", False))
        encrypted_contents = request.data.get("encrypted_contents", [])
        content = (request.data.get("content") or "").strip()
        reply_to_message_id = request.data.get("reply_to_message_id")
        if not dialogue_slug:
            return Response(
                {"error": "dialogue_slug is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=user)
        access = ConversationAccessPolicy.can_send_as_self(
            dialogue=dialogue,
            user=user,
        )
        if not access.allowed:
            return Response(
                {"error": access.message, "code": access.code},
                status=status.HTTP_403_FORBIDDEN,
            )
        boundary_payload = private_dialogue_boundary_response_payload(
            dialogue=dialogue,
            acting_user=user,
        )
        if boundary_payload:
            return Response(
                boundary_payload,
                status=status.HTTP_403_FORBIDDEN,
            )

        resolved_context = ConversationContextPolicy.resolve(dialogue)
        recipient_hidden_on_incoming = False
        recipient = None

        # Preserve existing Personal Messenger restore/hide behavior without
        # applying Personal DM marker semantics to Organization Direct.
        if resolved_context.kind != ConversationContextKind.ORGANIZATION_DIRECT:
            dialogue.release_inbound_block_on_outgoing(user)
            if not dialogue.is_group:
                recipient = dialogue.participants.exclude(id=user.id).first()
                if recipient:
                    if dialogue.should_restore_on_incoming_for_user(recipient):
                        dialogue.restore_dialogue(recipient)
                    recipient_hidden_on_incoming = (
                        dialogue.should_hide_incoming_for_user(recipient)
                    )

        # Personal Messenger keeps its existing sender-PoP behavior.
        # Organization Direct is backend-managed and must not depend on
        # Personal DM E2EE device-key readiness.
        if resolved_context.kind != ConversationContextKind.ORGANIZATION_DIRECT:
            header_device = (
                request.headers.get("X-Device-ID") or ""
            ).strip().lower()
            if not header_device:
                return Response(
                    {"error": "X-Device-ID header is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not is_sender_device_verified(
                user,
                header_device,
                dialogue_is_group=bool(dialogue.is_group),
            ):
                return Response(
                    {
                        "error": "Sender device is not verified.",
                        "code": "SENDER_DEVICE_UNVERIFIED",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        result = create_text_message(
            dialogue=dialogue,
            sender=user,
            is_encrypted=is_encrypted,
            content=content,
            encrypted_contents=encrypted_contents,
            recipient_hidden_on_incoming=recipient_hidden_on_incoming,
            recipient=recipient,
            reply_to_message_id=reply_to_message_id,
        )
        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )
        payload = result["payload"]
        message = payload["message"]

        if resolved_context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
            organization_context = resolved_context.organization_context
            mark_after_participant_message(
                context=organization_context,
                actor=user,
            )
            dialogue.deleted_by_users.remove(user)

        # IMPORTANT:
        # REST is the single creation path.
        # After successful REST creation, backend broadcasts the canonical realtime event.
        # This fixes iOS live group delivery without sending a second websocket create event.
        if dialogue.is_group:
            transaction.on_commit(
                lambda: broadcast_group_text_message(
                    message=message,
                    dialogue_slug=dialogue.slug,
                    plain_text=content,
                )
            )
        return Response(
            {
                "dialogue_slug": payload["dialogue_slug"],
                "message_id": payload["message_id"],
                "websocket_url": get_websocket_url(request),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="get-message", permission_classes=[IsAuthenticated])
    def get_message(self, request, pk=None):
        device_id = (
            request.query_params.get(
                "device_id",
                "",
            )
            or request.headers.get(
                "X-Device-ID",
                "",
            )
        ).strip().lower()
        message = get_object_or_404(
            Message.objects
            .select_related(
                "dialogue",
                "sender",
            )
            .prefetch_related(
                "seen_by_users",
                "encryptions",
                "pins",
            ),
            pk=pk,
        )
        access = ConversationAccessPolicy.can_view(
            dialogue=message.dialogue,
            user=request.user,
        )
        if not access.allowed:
            return Response(
                {
                    "error": access.message,
                    "code": access.code,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not (
            message.dialogue
            .visible_messages_for_user(request.user)
            .filter(id=message.id)
            .exists()
        ):
            return Response(
                {"error": "Message not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if (
            message.deleted_by_users
            .filter(
                id=request.user.id
            )
            .exists()
        ):
            return Response(
                {
                    "error":
                        "Message not found."
                },
                status=(
                    status.HTTP_404_NOT_FOUND
                ),
            )
        # Pending asynchronous Group Messenger media is not
        # available to other participants before Safety ALLOW.
        #
        # The sender may still resolve their own accepted upload
        # for recovery/debug flows.
        if (
            not message.is_delivery_ready
            and message.sender_id
            != request.user.id
        ):
            return Response(
                {
                    "error":
                        "Message not found."
                },
                status=(
                    status.HTTP_404_NOT_FOUND
                ),
            )
        serializer = MessageSerializer(
            message,
            context={
                "request":
                    request,
                "device_id":
                    device_id,
            },
        )
        return Response(
            serializer.data,
            status=(
                status.HTTP_200_OK
            ),
        )

