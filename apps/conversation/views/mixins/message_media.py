# apps/conversation/views/mixins/message_media.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.content_safety.serializers.jobs import ContentSafetyJobSerializer
from apps.conversation.models import Dialogue, Message, MessageEncryption
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
    ConversationSecurityMode,
    ConversationSecurityPolicy,
)
from apps.conversation.services.boundary_access import private_dialogue_boundary_response_payload
from apps.conversation.services.message_creation import (
    create_file_message,
    prepare_encrypted_file_request,
    validate_upload_input,
)
from apps.conversation.services.organization.direct_media import (
    create_organization_direct_media_message,
)
from apps.conversation.utils import get_websocket_url
from common.aws.s3_utils import get_file_url


class MessageMediaActionsMixin:
    @action(
        detail=False,
        methods=['post'],
        url_path='upload-file',
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_file(
        self,
        request,
    ):
        user = request.user
        dialogue_slug = (
            request.data.get(
                "dialogue_slug"
            )
        )
        uploaded_file = (
            request.FILES.get(
                "file"
            )
        )
        reply_to_message_id = (
            request.data.get(
                "reply_to_message_id"
            )
        )
        forwarded_from_message_id = (
            request.data.get(
                "forwarded_from_message_id"
            )
        )
        if not dialogue_slug:
            return Response(
                {
                    "error":
                        "Dialogue slug is required."
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )
        validation = validate_upload_input(
            uploaded_file=uploaded_file
        )
        if not validation.get(
            "ok"
        ):
            return Response(
                {
                    "error":
                        validation["message"],
                    "code":
                        validation["code"],
                },
                status=validation[
                    "status"
                ],
            )
        validation_payload = (
            validation[
                "payload"
            ]
        )
        field_name = (
            validation_payload[
                "field_name"
            ]
        )
        file_type = (
            validation_payload[
                "file_type"
            ]
        )
        dialogue = get_object_or_404(
            Dialogue,
            slug=dialogue_slug,
        )
        resolved_context = ConversationContextPolicy.resolve(dialogue)
        security = ConversationSecurityPolicy.resolve(dialogue)

        if resolved_context.kind != ConversationContextKind.ORGANIZATION_DIRECT:
            access = ConversationAccessPolicy.can_send_as_self(
                dialogue=dialogue,
                user=user,
            )
            if not access.allowed:
                return Response(
                    {"error": access.message, "code": access.code},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if security.mode == ConversationSecurityMode.END_TO_END_ENCRYPTED:
            boundary_payload = private_dialogue_boundary_response_payload(
                dialogue=dialogue,
                acting_user=user,
            )
            if boundary_payload:
                return Response(
                    boundary_payload,
                    status=status.HTTP_403_FORBIDDEN,
                )
        # --------------------------------------------------------------
        # Forward source validation
        # --------------------------------------------------------------
        forwarded_from_message = None
        if forwarded_from_message_id:
            try:
                forwarded_from_message = (
                    Message.objects
                    .select_related(
                        "dialogue",
                        "sender",
                    )
                    .get(
                        id=(
                            forwarded_from_message_id
                        )
                    )
                )
            except Message.DoesNotExist:
                return Response(
                    {
                        "error":
                            "Forward source message not found.",
                        "code":
                            "FORWARD_SOURCE_NOT_FOUND",
                    },
                    status=(
                        status.HTTP_404_NOT_FOUND
                    ),
                )
            if ConversationContextPolicy.resolve(
                forwarded_from_message.dialogue
            ).is_organization:
                return Response(
                    {
                        "error": (
                            "Forwarding from Organization conversations "
                            "is not available yet."
                        ),
                        "code": "ORGANIZATION_FORWARDING_NOT_AVAILABLE",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if not ConversationAccessPolicy.can_view(
                dialogue=forwarded_from_message.dialogue,
                user=user,
            ).allowed:
                return Response(
                    {
                        "error":
                            (
                                "You do not have access to "
                                "the forward source message."
                            ),
                        "code":
                            "FORWARD_SOURCE_FORBIDDEN",
                    },
                    status=(
                        status.HTTP_403_FORBIDDEN
                    ),
                )
            if not (
                forwarded_from_message.dialogue
                .visible_messages_for_user(user)
                .filter(id=forwarded_from_message.id)
                .exists()
            ):
                return Response(
                    {
                        "error":
                            (
                                "Forward source message is "
                                "not visible to you."
                            ),
                        "code":
                            "FORWARD_SOURCE_NOT_VISIBLE",
                    },
                    status=(
                        status.HTTP_403_FORBIDDEN
                    ),
                )
            if not (
                forwarded_from_message
                .is_delivery_ready
            ):
                return Response(
                    {
                        "error":
                            (
                                "Forward source message is "
                                "not ready for delivery."
                            ),
                        "code":
                            "FORWARD_SOURCE_NOT_READY",
                    },
                    status=(
                        status.HTTP_409_CONFLICT
                    ),
                )
            if forwarded_from_message.is_system:
                return Response(
                    {
                        "error":
                            "System messages cannot be forwarded.",
                        "code":
                            "INVALID_FORWARD_SOURCE",
                    },
                    status=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                )
        if (
            resolved_context.kind == ConversationContextKind.ORGANIZATION_DIRECT
            and forwarded_from_message is not None
        ):
            return Response(
                {
                    "error": "Forwarding to Organization conversations is not available yet.",
                    "code": "ORGANIZATION_FORWARDING_NOT_AVAILABLE",
                },
                status=status.HTTP_409_CONFLICT,
            )

        # --------------------------------------------------------------
        # Dialogue restore / inbound state
        # --------------------------------------------------------------
        recipient_hidden_on_incoming = False
        recipient = None
        if resolved_context.kind != ConversationContextKind.ORGANIZATION_DIRECT:
            dialogue.release_inbound_block_on_outgoing(user)

        if resolved_context.kind == ConversationContextKind.PERSONAL_DIRECT:
            recipient = (
                dialogue.participants
                .exclude(
                    id=user.id
                )
                .first()
            )
            if recipient:
                if (
                    dialogue
                    .should_restore_on_incoming_for_user(
                        recipient
                    )
                ):
                    dialogue.restore_dialogue(
                        recipient
                    )
                recipient_hidden_on_incoming = (
                    dialogue
                    .should_hide_incoming_for_user(
                        recipient
                    )
                )
        # --------------------------------------------------------------
        # Sender PoP
        # --------------------------------------------------------------
        header_device = (
            request.headers.get(
                "X-Device-ID"
            )
            or ""
        ).strip().lower()
        if not header_device:
            return Response(
                {
                    "error":
                        "X-Device-ID header is required."
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )
        if not is_sender_device_verified(
            user,
            header_device,
            dialogue_is_group=(
                security.mode == ConversationSecurityMode.BACKEND_MANAGED
            ),
        ):
            return Response(
                {
                    "error":
                        "Sender device is not verified.",
                    "code":
                        "SENDER_DEVICE_UNVERIFIED",
                },
                status=(
                    status.HTTP_403_FORBIDDEN
                ),
            )
        # --------------------------------------------------------------
        # E2EE request normalization
        # --------------------------------------------------------------
        encrypted_prepare = (
            prepare_encrypted_file_request(
                is_encrypted_file=(
                    str(
                        request.data.get(
                            "is_encrypted_file",
                            "",
                        )
                    )
                    .strip()
                    .lower()
                    in (
                        "true",
                        "1",
                        "yes",
                    )
                ),
                encrypted_for_device=(
                    request.data.get(
                        "encrypted_for_device"
                    )
                ),
                aes_key_encrypted=(
                    request.data.get(
                        "aes_key_encrypted"
                    )
                ),
                encrypted_keys_per_device=(
                    request.data.get(
                        "encrypted_keys_per_device"
                    )
                ),
            )
        )
        if not encrypted_prepare.get(
            "ok"
        ):
            return Response(
                {
                    "error":
                        encrypted_prepare[
                            "message"
                        ],
                    "code":
                        encrypted_prepare[
                            "code"
                        ],
                },
                status=(
                    encrypted_prepare[
                        "status"
                    ]
                ),
            )
        encrypted_payload = (
            encrypted_prepare[
                "payload"
            ]
        )
        # --------------------------------------------------------------
        # Create
        # --------------------------------------------------------------
        create_kwargs = {
            "uploaded_file": uploaded_file,
            "field_name": field_name,
            "is_encrypted_file": encrypted_payload["is_encrypted_file"],
            "encrypted_for_device": encrypted_payload["encrypted_for_device"],
            "aes_key_encrypted_bytes": encrypted_payload["aes_key_encrypted_bytes"],
            "encrypted_keys_per_device": encrypted_payload["encrypted_keys_per_device"],
            "reply_to_message_id": reply_to_message_id,
        }

        if resolved_context.kind == ConversationContextKind.ORGANIZATION_DIRECT:
            result = create_organization_direct_media_message(
                context=resolved_context.organization_context,
                acting_user=user,
                **create_kwargs,
            )
        else:
            result = create_file_message(
                dialogue=dialogue,
                sender=user,
                recipient_hidden_on_incoming=recipient_hidden_on_incoming,
                recipient=recipient,
                forwarded_from_message=forwarded_from_message,
                **create_kwargs,
            )
        if not result.get(
            "ok"
        ):
            return Response(
                {
                    "error":
                        result["message"],
                    "code":
                        result["code"],
                },
                status=result[
                    "status"
                ],
            )
        payload = result[
            "payload"
        ]
        message = payload[
            "message"
        ]
        content_safety_jobs = (
            payload.get(
                "content_safety_jobs"
            )
            or []
        )
        # --------------------------------------------------------------
        # File URL
        # --------------------------------------------------------------
        stored_file = getattr(
            message,
            field_name,
        )
        file_key = getattr(
            stored_file,
            "name",
            None,
        )
        file_url = (
            get_file_url(
                file_key
            )
            if (
                file_key
                and not message.is_encrypted_file
            )
            else None
        )
        # --------------------------------------------------------------
        # Response
        # --------------------------------------------------------------
        response_payload = {
            "file_url":
                file_url,
            "message_id":
                payload[
                    "message_id"
                ],
            "file_type":
                file_type,
            "dialogue_slug":
                payload[
                    "dialogue_slug"
                ],
            "is_encrypted_file":
                bool(
                    message.is_encrypted_file
                ),
            "websocket_url":
                get_websocket_url(
                    request
                ),
        }
        if content_safety_jobs:
            response_payload[
                "content_safety_jobs"
            ] = (
                ContentSafetyJobSerializer(
                    content_safety_jobs,
                    many=True,
                ).data
            )
            return Response(
                response_payload,
                status=(
                    status.HTTP_202_ACCEPTED
                ),
            )
        return Response(
            response_payload,
            status=(
                status.HTTP_201_CREATED
            ),
        )

    @action(detail=True, methods=['get'], url_path='access-media', permission_classes=[IsAuthenticated])
    def access_media(self, request, pk=None):
        user = request.user
        device_id = (request.headers.get("X-Device-ID") or "").strip().lower()
        if not device_id:
            return Response({"error": "Missing device ID."}, status=status.HTTP_400_BAD_REQUEST)
        message = get_object_or_404(Message, pk=pk, dialogue__participants=user)
        if not message.is_encrypted_file:
            return Response({"error": "This media is not encrypted."}, status=status.HTTP_400_BAD_REQUEST)
        media_type = request.query_params.get("media_type")
        if media_type not in ["image", "video", "file", "audio"]:
            return Response({"error": "Invalid media type."}, status=status.HTTP_400_BAD_REQUEST)
        mode = (request.query_params.get("mode") or "inline").strip().lower()  # "inline" | "download"
        media_field = getattr(message, media_type, None)
        if not media_field:
            return Response({"error": f"{media_type} not found on this message."}, status=status.HTTP_404_NOT_FOUND)
        enc_entry = MessageEncryption.objects.filter(message=message, device_id=device_id).first()
        if not enc_entry:
            user_dev_ids = list(UserDeviceKey.objects.filter(user=user).values_list("device_id", flat=True))
            if user_dev_ids:
                enc_entry = MessageEncryption.objects.filter(message=message, device_id__in=user_dev_ids).first()
        if not enc_entry:
            return Response({"error": "Encrypted key not found for this device or user devices."}, status=status.HTTP_403_FORBIDDEN)
        key = getattr(media_field, "name", None)
        if not key:
            return Response({"error": "Media key missing."}, status=status.HTTP_404_NOT_FOUND)
        force_download = (mode == "download")
        signed_url = get_file_url(key=key, expires_in=None, force_download=force_download)
        return Response(
            {
                "download_url": signed_url,
                "encrypted_aes_key": enc_entry.encrypted_content,
            },
            status=status.HTTP_200_OK
        )

