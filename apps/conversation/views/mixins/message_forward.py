# apps/conversation/views/mixins/message_forward.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import base64

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversation.models import Dialogue
from apps.conversation.services.boundary_access import (
    private_dialogue_boundary_response_payload,
    should_send_conversation_notification,
)
from apps.conversation.services.event_contracts import (
    build_file_message_event_data,
    build_group_chat_message_data,
)
from apps.conversation.services.message_forward import (
    build_forward_preview,
    create_forwarded_message_backend_assisted,
    create_forwarded_text_client_decrypted_group,
    create_forwarded_text_client_reencrypted,
)
from apps.conversation.services.realtime_dispatch import conv_group_send
from common.aws.s3_utils import get_file_url


class MessageForwardActionsMixin:
    @action(detail=False, methods=['post'], url_path='forward-message', permission_classes=[IsAuthenticated])
    def forward_message(self, request):
        source_message_id = request.data.get("source_message_id")
        target_dialogue_slug = (request.data.get("target_dialogue_slug") or "").strip()
        if target_dialogue_slug:
            target_dialogue = (
                Dialogue.objects
                .filter(slug=target_dialogue_slug, participants=request.user)
                .prefetch_related("participants")
                .first()
            )
            if target_dialogue:
                boundary_payload = private_dialogue_boundary_response_payload(
                    dialogue=target_dialogue,
                    acting_user=request.user,
                )
                if boundary_payload:
                    return Response(
                        boundary_payload,
                        status=status.HTTP_403_FORBIDDEN,
                    )
        result = create_forwarded_message_backend_assisted(
            source_message_id=source_message_id,
            target_dialogue_slug=target_dialogue_slug,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {
                    "error": result["message"],
                    "code": result["code"],
                    "extra": result.get("extra", {}),
                },
                status=result["status"],
            )
        payload = result["payload"]
        message = payload["message"]
        dialogue = payload["dialogue"]
        # Group target is the only backend-assisted mode for now
        if payload["kind"] == "text":
            plain_text = ""
            try:
                raw = message.content_encrypted
                if isinstance(raw, memoryview):
                    raw = raw.tobytes()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="ignore")
                plain_text = base64.b64decode(raw).decode("utf-8")
            except Exception:
                plain_text = ""
            realtime_data = build_group_chat_message_data(
                message=message,
                plain_text=plain_text,
                reply_preview=None,
                forward_preview=build_forward_preview(message=message),
            )
            for uid in dialogue.participants.values_list("id", flat=True):
                conv_group_send(
                    f"user_{uid}",
                    "chat_message",
                    realtime_data,
                )
            for participant in dialogue.participants.exclude(id=request.user.id).only("id"):
                if not should_send_conversation_notification(
                    actor=request.user,
                    recipient=participant,
                ):
                    continue
                conv_group_send(
                    f"user_{participant.id}",
                    "unread_count_update",
                    {
                        "payload": [
                            {
                                "dialogue_slug": dialogue.slug,
                                "unread_count": 1,
                                "sender_id": request.user.id,
                            }
                        ]
                    },
                )
        else:
            file_field = payload.get("file_field")
            file_type = file_field or "file"
            file_url = None
            if file_field:
                stored_field = getattr(message, file_field, None)
                file_key = getattr(stored_field, "name", None) if stored_field else None
                file_url = get_file_url(file_key) if file_key else None
            realtime_data = build_file_message_event_data(
                message=message,
                dialogue_slug=dialogue.slug,
                file_type=file_type,
                file_url=file_url,
                reply_preview=None,
                forward_preview=build_forward_preview(message=message),
            )
            for uid in dialogue.participants.values_list("id", flat=True):
                conv_group_send(
                    f"user_{uid}",
                    "file_message",
                    realtime_data,
                )
            for uid in dialogue.participants.exclude(id=request.user.id).values_list("id", flat=True):
                conv_group_send(
                    f"user_{uid}",
                    "unread_count_update",
                    {
                        "payload": [
                            {
                                "dialogue_slug": dialogue.slug,
                                "unread_count": 1,
                                "sender_id": request.user.id,
                            }
                        ]
                    },
                )
        return Response(
            {
                "message": "Message forwarded successfully.",
                "forward_mode": payload["forward_mode"],
                "kind": payload["kind"],
                "dialogue_slug": payload["dialogue_slug"],
                "message_id": payload["message_id"],
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="forward-message-client-reencrypted",
        permission_classes=[IsAuthenticated],
    )
    def forward_message_client_reencrypted(self, request):
        """
        Forward text into an E2EE private dialogue.
        The client sends encrypted envelopes.
        Backend never receives plaintext.
        """
        source_message_id = request.data.get("source_message_id")
        target_dialogue_slug = (request.data.get("target_dialogue_slug") or "").strip()
        boundary_payload = None
        if target_dialogue_slug:
            target_dialogue = (
                Dialogue.objects
                .filter(slug=target_dialogue_slug, participants=request.user)
                .prefetch_related("participants")
                .first()
            )
            if target_dialogue:
                boundary_payload = private_dialogue_boundary_response_payload(
                    dialogue=target_dialogue,
                    acting_user=request.user,
                )
        if boundary_payload:
            return Response(
                boundary_payload,
                status=status.HTTP_403_FORBIDDEN,
            )
        encrypted_contents = request.data.get("encrypted_contents") or []
        result = create_forwarded_text_client_reencrypted(
            source_message_id=source_message_id,
            target_dialogue_slug=target_dialogue_slug,
            encrypted_contents=encrypted_contents,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {
                    "error": result["message"],
                    "code": result["code"],
                    "extra": result.get("extra", {}),
                },
                status=result["status"],
            )
        payload = result["payload"]
        message = payload["message"]
        dialogue = payload["dialogue"]
        # Minimal realtime payload. iOS fetches authoritative message by id.
        realtime_data = {
            "id": message.id,
            "dialogue": dialogue.id,
            "dialogue_slug": dialogue.slug,
            "sender": {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
            },
            "timestamp": message.timestamp.isoformat(),
            "edited_at": None,
            "is_edited": False,
            "seen_by_users": [],
            "seen_count": 0,
            "seen_count_others": 0,
            "is_delivered": False,
            "reply_to_message_id": None,
            "reply_preview": None,
            "is_forwarded": True,
            "forwarded_from_message_id": message.forwarded_from_id,
            "forward_preview": build_forward_preview(message=message),
            "reaction_summary": None,
            "content_encrypted": None,
            "decrypted_content": None,
            "aes_key_encrypted": None,
            "encrypted_for_device": None,
            "image": None,
            "video": None,
            "file": None,
            "audio": None,
            "image_url": None,
            "image_download_url": None,
            "video_url": None,
            "video_download_url": None,
            "file_url": None,
            "file_download_url": None,
            "audio_url": None,
            "audio_download_url": None,
            "is_system": False,
            "system_event": None,
            "self_destruct_at": None,
            "is_encrypted": True,
            "is_encrypted_file": False,
            "is_pinned": False,
            "pinned_position": None,
        }
        for uid in dialogue.participants.values_list("id", flat=True):
            conv_group_send(
                f"user_{uid}",
                "chat_message",
                realtime_data,
            )
        for uid in dialogue.participants.exclude(id=request.user.id).values_list("id", flat=True):
            conv_group_send(
                f"user_{uid}",
                "unread_count_update",
                {
                    "payload": [
                        {
                            "dialogue_slug": dialogue.slug,
                            "unread_count": 1,
                            "sender_id": request.user.id,
                        }
                    ]
                },
            )
        return Response(
            {
                "message": "Message forwarded successfully.",
                "forward_mode": payload["forward_mode"],
                "kind": payload["kind"],
                "dialogue_slug": payload["dialogue_slug"],
                "message_id": payload["message_id"],
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="forward-message-client-decrypted-group",
        permission_classes=[IsAuthenticated],
    )
    def forward_message_client_decrypted_group(self, request):
        """
        Forward private text into a backend-managed group.
        The client decrypts source text first, then backend stores group plaintext.
        """
        source_message_id = request.data.get("source_message_id")
        target_dialogue_slug = (request.data.get("target_dialogue_slug") or "").strip()
        content = request.data.get("content") or ""
        result = create_forwarded_text_client_decrypted_group(
            source_message_id=source_message_id,
            target_dialogue_slug=target_dialogue_slug,
            content=content,
            acting_user=request.user,
        )
        if not result.get("ok"):
            return Response(
                {
                    "error": result["message"],
                    "code": result["code"],
                    "extra": result.get("extra", {}),
                },
                status=result["status"],
            )
        payload = result["payload"]
        message = payload["message"]
        dialogue = payload["dialogue"]
        plain_text = payload.get("plain_text") or ""
        realtime_data = build_group_chat_message_data(
            message=message,
            plain_text=plain_text,
            reply_preview=None,
            forward_preview=build_forward_preview(message=message),
        )
        for uid in dialogue.participants.values_list("id", flat=True):
            conv_group_send(
                f"user_{uid}",
                "chat_message",
                realtime_data,
            )
        for participant in dialogue.participants.exclude(id=request.user.id).only("id"):
            if not should_send_conversation_notification(
                actor=request.user,
                recipient=participant,
            ):
                continue
            conv_group_send(
                f"user_{participant.id}",
                "unread_count_update",
                {
                    "payload": [
                        {
                            "dialogue_slug": dialogue.slug,
                            "unread_count": 1,
                            "sender_id": request.user.id,
                        }
                    ]
                },
            )
        return Response(
            {
                "message": "Message forwarded successfully.",
                "forward_mode": payload["forward_mode"],
                "kind": payload["kind"],
                "dialogue_slug": payload["dialogue_slug"],
                "message_id": payload["message_id"],
            },
            status=status.HTTP_201_CREATED,
        )
