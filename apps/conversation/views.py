# apps/conversation/views.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import (
    Max,
    Q,
    Value,
    DateTimeField,
    OuterRef,
    Subquery,
    IntegerField,
    Case,
    When,
)
from django.db import transaction
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
import base64
import json

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import asyncio
from apps.core.websocket.services.redis_online_manager import get_last_seen, get_online_status_for_users
from datetime import datetime
from django.utils.timesince import timesince
from rest_framework.renderers import JSONRenderer

from common.aws.s3_utils import get_file_url
from .models import (
    Dialogue,
    Message,
    MessageSearchIndex,
    MessageEncryption,
    UserDialogueMarker,
    DialogueParticipant,
    DialoguePin,
)
from .serializers import (
    DialogueSerializer,
    MessageSerializer,
    UserDialogueMarkerSerializer,
    DialogueParticipantSerializer,
    UpdateGroupInfoSerializer,
    CreateGroupSerializer,
    DialoguePinSerializer,
    MessagePinSerializer,
)
from .permissions import ConversationAccessPermission, IsDialogueParticipant
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.accounts.models.devices import UserDeviceKey
from apps.conversation.utils import get_websocket_url
from common.mime_type_validator import validate_file_type, is_unsafe_file
from apps.core.security.decorators import require_litshield_access

# Services
from apps.conversation.services.read_delivery import (
    mark_message_delivered_for_user,
    mark_dialogue_read_for_user,
    build_mark_as_read_realtime_payload,
    build_unread_count_snapshot_payload,
)
from apps.conversation.services.message_mutations import (
    edit_message_content,
    soft_delete_message_for_user,
    hard_delete_message_for_user,
    build_message_soft_deleted_realtime_payload,
)
from apps.conversation.services.message_creation import (
    create_text_message,
    validate_upload_input,
    create_file_message,
    prepare_encrypted_file_request,
)
from apps.conversation.services.group_domain import (
    add_group_participant,
    remove_group_participant,
    promote_group_participant_to_elder,
    demote_group_elder_to_participant,
    resign_group_elder_role,
    leave_group_as_participant,
    transfer_group_founder,
    build_group_role_changed_system_text,
)
from apps.conversation.services.dialogue_lifecycle import (
    create_or_get_private_dialogue,
    create_group_dialogue,
    smart_delete_dialogue_for_user,
)
from apps.conversation.services.event_contracts import (
    build_delivery_event_data,
    build_dm_edit_message_data,
    build_group_added_event_data,
    build_group_edit_message_data,
    build_group_left_event_data,
    build_group_removed_event_data,
    build_founder_transferred_event_data,
    build_hard_delete_event_data,
    build_system_chat_message_data,
    build_message_pin_event_data,
    build_message_unpin_event_data,
    build_group_chat_message_data,
    build_file_message_event_data,
    build_dialogue_pinned_event_data,
    build_dialogue_unpinned_event_data,
    build_message_reaction_summary_event_data,
    build_message_reaction_toggled_event_data,
)
from apps.conversation.services.dialogue_pins import (
    pin_dialogue_for_user,
    unpin_dialogue_for_user,
    list_pinned_dialogues_for_user,
)
from apps.conversation.services.message_pins import (
    pin_message_for_dialogue,
    unpin_message_for_dialogue,
    list_pinned_messages_for_dialogue,
)
from apps.conversation.services.message_forward import (
    build_forward_preview,
    create_forwarded_message_backend_assisted,
    create_forwarded_text_client_reencrypted,
    create_forwarded_text_client_decrypted_group,
)
from apps.conversation.services.message_reactions import (
    toggle_message_reaction,
    get_message_reaction_summary_for_user,
    list_message_reactors,
)
from apps.conversation.services.realtime_dispatch import (
    conv_group_send,
    conv_multi_group_send,
    conversation_dialogue_group_name,
)
from apps.conversation.services.event_contracts import (
    build_group_updated_event_data,
)
from apps.conversation.services.realtime_dispatch import broadcast_group_text_message
from apps.conversation.services.boundary_access import (
    can_create_private_dialogue,
    can_add_user_to_group,
    private_dialogue_boundary_response_payload,
    conversation_boundary_error_payload,
    should_send_conversation_notification,
    CONVERSATION_INTERACTION_UNAVAILABLE_CODE,
)
from apps.core.boundaries.constants import BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE
from apps.core.boundaries.services.policy import BoundaryPolicy

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model
CustomUser = get_user_model()


# REALTIME HELPERS ------------------------------------------------------------------------
def conv_dispatch_payload(event: str, data: dict | None = None):
    """
    Canonical conversation dispatch payload for channel_layer.group_send.
    """
    return {
        "type": "dispatch_event",
        "app": "conversation",
        "event": event,
        "data": data or {},
    }


def conv_group_send(group_name: str, event: str, data: dict | None = None):
    """
    Send one canonical conversation realtime event to one group.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        conv_dispatch_payload(event, data),
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

    This is intentionally separate from system messages:
    - system message updates the chat stream
    - group_updated updates header/list/avatar/roles/member count
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
    
# SYSTEM MESSAGES ------------------------------------------------------------------------
def send_system_message(dialogue, sender, system_event, content):
    plain_text = (content or "").strip()
    if not plain_text:
        return None

    # Store plaintext in current DB format (base64 bytes)
    base64_str = base64.b64encode(plain_text.encode("utf-8")).decode("utf-8")
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
        f"dialogue_{dialogue.slug}",
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

# DIALOGUE VIEWSET -------------------------------------------------------------------------
class DialogueViewSet(viewsets.ModelViewSet):
    queryset = Dialogue.objects.all()
    serializer_class = DialogueSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'
    
    def _base_qs(self):
        # base filter for current user and not deleted
        return (Dialogue.objects
                .filter(participants=self.request.user)
                .exclude(deleted_by_users=self.request.user))

    def _with_last_activity(self, qs):
        """
        Order dialogues by:
        1) pinned dialogues first (per-user)
        2) pinned position ascending
        3) latest visible non-system activity
        4) created_at fallback

        Notes:
        - pin state is per-user
        - activity is visibility-aware per-user
        """
        user = self.request.user

        visible_last_message_ts = Subquery(
            Message.objects
            .filter(dialogue=OuterRef("pk"), is_system=False)
            .exclude(deleted_by_users=user)
            .order_by("-timestamp")
            .values("timestamp")[:1]
        )

        pinned_position_subquery = Subquery(
            DialoguePin.objects
            .filter(user=user, dialogue=OuterRef("pk"))
            .values("position")[:1],
            output_field=IntegerField(),
        )

        return (
            qs.annotate(
                last_msg_ts=visible_last_message_ts,
                last_activity=Coalesce("last_msg_ts", "created_at"),
                pinned_position=pinned_position_subquery,
                is_pinned_sort=Case(
                    When(pinned_position__isnull=False, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )
            .order_by(
                "-is_pinned_sort",
                "pinned_position",
                "-last_activity",
                "-created_at",
            )
            .prefetch_related("participants", "participants_roles", "marked_users")
        )

    def get_queryset(self):
        # used by default list/retrieve
        base = self._base_qs()
        return self._with_last_activity(base)

    # Helper methods ---------------------------------------
    def _serialize_single_dialogue(self, request, dialogue, device_id=None):
        """
        Serialize one dialogue with the same annotated ordering fields.
        """
        hydrated = self._with_last_activity(
            Dialogue.objects.filter(pk=dialogue.pk)
        ).first()

        serializer = DialogueSerializer(
            hydrated or dialogue,
            context={"request": request, "device_id": device_id},
        )
        return serializer.data
    
    # ---------------------------------------
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
        
    # ---------------------------------------
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
        
    # ---------------------------------------   
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
        
        
    # ---------------------------------------
    @action(detail=False, methods=['post'], url_path='create-group', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def create_group(self, request):
        serializer = CreateGroupSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        group_name = serializer.validated_data["group_name"]
        group_image = serializer.validated_data.get("group_image")

        result = create_group_dialogue(
            acting_user=request.user,
            group_name=group_name,
            group_image=group_image,
        )

        if not result.get("ok"):
            return Response(
                {
                    "error": result["message"],
                    "code": result["code"],
                },
                status=result["status"],
            )

        dialogue = result["payload"]["dialogue"]
        output_serializer = DialogueSerializer(
            dialogue,
            context={"request": request},
        )

        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
        
    # Update Group Image Action ---------------
    @action(detail=True, methods=["post"], url_path="update-group-image", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def update_group_image(self, request, **kwargs):
        dialogue = self.get_object()

        if not dialogue.is_group:
            return Response(
                {"detail": "Only group dialogues can have images."},
                status=status.HTTP_400_BAD_REQUEST
            )

        participant = DialogueParticipant.objects.filter(
            dialogue=dialogue,
            user=request.user
        ).first()

        if not participant:
            return Response(
                {"detail": "You are not a participant of this group."},
                status=status.HTTP_404_NOT_FOUND
            )

        if participant.role not in ["founder", "elder"]:
            return Response(
                {"detail": "You don't have permission to update the group image."},
                status=status.HTTP_403_FORBIDDEN
            )

        group_image = request.FILES.get("group_image")

        if not group_image:
            return Response(
                {"detail": "No image uploaded."},
                status=status.HTTP_400_BAD_REQUEST
            )

        dialogue.group_image = group_image
        dialogue.group_avatar_version = (dialogue.group_avatar_version or 0) + 1
        dialogue.save(update_fields=["group_image", "group_avatar_version"])

        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="group_image_updated",
            actor_user=request.user,
        )

        serializer = DialogueSerializer(dialogue, context={"request": request})

        return Response(
            {
                "detail": "Group image updated successfully.",
                "dialogue": serializer.data,
            },
            status=status.HTTP_200_OK
        )

    # Update Group Name & ... Action ---------------
    @action(detail=True, methods=["post", "patch"], url_path="update-group-info", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def update_group_info(self, request, **kwargs):
        dialogue = self.get_object()
        if not getattr(dialogue, "is_group", False):
            return Response({"detail": "Only group dialogues can be updated."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            participant = DialogueParticipant.objects.get(dialogue=dialogue, user=request.user)
            if participant.role not in ["founder", "elder"]:
                return Response({"detail": "You don't have permission to update group info."}, status=status.HTTP_403_FORBIDDEN)
        except DialogueParticipant.DoesNotExist:
            return Response({"detail": "You are not a participant of this group."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UpdateGroupInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        field_map = {
            "group_name": "group_name",
        }

        updated_fields = {}
        unsupported_keys = []
        with transaction.atomic():
            for client_key, value in payload.items():
                model_field = field_map.get(client_key)
                if not model_field:
                    unsupported_keys.append(client_key)
                    continue
                if not hasattr(dialogue, model_field):
                    unsupported_keys.append(client_key)
                    continue

                # Skip no-op updates
                current_val = getattr(dialogue, model_field, None)
                if isinstance(value, str):
                    value = value.strip()
                if value == current_val:
                    continue

                setattr(dialogue, model_field, value)
                updated_fields[model_field] = value

            if not updated_fields:
                if unsupported_keys:
                    return Response(
                        {"detail": "No supported fields provided.", "unsupported": unsupported_keys},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return Response({"detail": "No changes detected."}, status=status.HTTP_200_OK)
            try:
                dialogue.save(update_fields=list(updated_fields.keys()))
            except Exception:
                dialogue.save()

        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="group_info_updated",
            actor_user=request.user,
        )

        return Response(
            {
                "detail": "Group info updated successfully.",
                "updated": updated_fields,
                "unsupported": unsupported_keys or [],
            },
            status=status.HTTP_200_OK,
        )
        
    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='smart-delete', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def smart_delete_dialogue(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)

        result = smart_delete_dialogue_for_user(
            dialogue=dialogue,
            acting_user=request.user,
        )

        if not result.get("ok"):
            return Response(
                {'error': result["message"], 'code': result["code"]},
                status=result["status"]
            )

        payload = result["payload"]
        return Response(
            {'message': payload["message"]},
            status=status.HTTP_200_OK
        )

    # ---------------------------------------
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

        serializer = DialogueSerializer(dialogue, context={"request": request})
        json_data = JSONRenderer().render(serializer.data)
        parsed_data = json.loads(json_data)
        parsed_data["my_role"] = "participant"

        # 1) Targeted realtime event
        conv_group_send(
            f"user_{participant.id}",
            "group_added",
            build_group_added_event_data(dialogue=parsed_data),
        )

        # 2) System message after targeted event
        send_system_message(
            dialogue,
            request.user,
            "joined",
            f"{participant.username} joined the group.",
        )

        _broadcast_group_updated(
            dialogue=dialogue,
            request=request,
            reason="member_added",
            actor_user=request.user,
            target_user=participant,
        )

        return Response(
            {'message': f'{participant.username} added to the group.'},
            status=status.HTTP_200_OK
        )

    # ---------------------------------------
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
            
    # ---------------------------------------
    @action(detail=True, methods=['get'], url_path='participants', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def get_group_participants(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        participants = DialogueParticipant.objects.filter(dialogue=dialogue).select_related('user')
        serializer = DialogueParticipantSerializer(
            participants,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    # ---------------------------------------
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
    
        
    # ---------------------------------------
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
    
    
    # ---------------------------------------
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

    
    # ---------------------------------------
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
                    
    # ---------------------------------------
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

    # Get Last Seen Users -------------------
    @action(detail=True, methods=['get'], url_path='last-seen', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def get_last_seen_view(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug)
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


    # Get Unread Counts -------------------------
    @action(detail=False, methods=["get"], url_path="unread-counts", permission_classes=[IsAuthenticated])
    def get_unread_counts(self, request):
        user = request.user
        dialogues = Dialogue.objects.filter(participants=user).exclude(deleted_by_users=user)

        results = []
        for dialogue in dialogues:
            results.append({
                "dialogue_slug": dialogue.slug,
                "unread_count": dialogue.unread_messages_for_user(user).count(),
            })

        return Response(build_unread_count_snapshot_payload(results))

    # ---------------------------------------
    @action(detail=True, methods=["post"], url_path="pin-dialogue", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def pin_dialogue(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)

        result = pin_dialogue_for_user(
            dialogue=dialogue,
            acting_user=request.user,
        )

        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )

        device_id = (
            request.data.get("device_id")
            or request.query_params.get("device_id")
            or request.headers.get("X-Device-ID", "")
        )

        serialized_dialogue = self._serialize_single_dialogue(
            request=request,
            dialogue=dialogue,
            device_id=device_id,
        )

        # Push realtime update only to the acting user's sessions
        conv_group_send(
            f"user_{request.user.id}",
            "dialogue_pinned",
            build_dialogue_pinned_event_data(dialogue=serialized_dialogue),
        )

        return Response(
            {
                "message": result["payload"]["message"],
                "dialogue": serialized_dialogue,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------
    @action(detail=True, methods=["post"], url_path="unpin-dialogue", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def unpin_dialogue(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)

        result = unpin_dialogue_for_user(
            dialogue=dialogue,
            acting_user=request.user,
        )

        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )

        device_id = (
            request.data.get("device_id")
            or request.query_params.get("device_id")
            or request.headers.get("X-Device-ID", "")
        )

        serialized_dialogue = self._serialize_single_dialogue(
            request=request,
            dialogue=dialogue,
            device_id=device_id,
        )

        # Push realtime update only to the acting user's sessions
        conv_group_send(
            f"user_{request.user.id}",
            "dialogue_unpinned",
            build_dialogue_unpinned_event_data(dialogue=serialized_dialogue),
        )

        return Response(
            {
                "message": result["payload"]["message"],
                "dialogue": serialized_dialogue,
            },
            status=status.HTTP_200_OK,
        )
        
        
    # Pinned Dialogues ---------------------------------------
    @action(detail=False, methods=["get"], url_path="pinned-dialogues", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def pinned_dialogues(self, request):
        result = list_pinned_dialogues_for_user(
            acting_user=request.user,
        )

        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )

        pins = result["payload"]["pins"]

        serializer = DialoguePinSerializer(
            pins,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "count": result["payload"]["count"],
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
        
    # Pinned Messages ---------------------------------------
    @action(detail=True, methods=["get"], url_path="pinned-messages", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def pinned_messages(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=request.user)

        result = list_pinned_messages_for_dialogue(
            dialogue=dialogue,
            acting_user=request.user,
        )

        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )

        device_id = (
            request.query_params.get("device_id", "")
            or request.headers.get("X-Device-ID", "")
        ).strip().lower()

        serializer = MessagePinSerializer(
            result["payload"]["pins"],
            many=True,
            context={"request": request, "device_id": device_id},
        )

        return Response(
            {
                "count": result["payload"]["count"],
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
        
        
        
# MESSAGE VIEWSET -------------------------------------------------------------------------
class MessageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ConversationAccessPermission, IsDialogueParticipant]
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def list(self, request, dialogue_slug=None):
        """ Retrieve messages for a dialogue with pagination """
        dialogue_slug = request.query_params.get("dialogue_slug")
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 20))
        device_id = request.query_params.get("device_id", "")
        device_id = device_id.strip().lower()

        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=request.user)

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

    # -------------------------------------------------------------------------------------------------
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

        boundary_payload = private_dialogue_boundary_response_payload(
            dialogue=dialogue,
            acting_user=user,
        )

        if boundary_payload:
            return Response(
                boundary_payload,
                status=status.HTTP_403_FORBIDDEN,
            )
            
        # Re-open dialogue on first outgoing message if needed.
        dialogue.release_inbound_block_on_outgoing(user)

        recipient_hidden_on_incoming = False
        recipient = None

        # Private chat restore/hide logic.
        if not dialogue.is_group:
            recipient = dialogue.participants.exclude(id=user.id).first()
            if recipient:
                if dialogue.should_restore_on_incoming_for_user(recipient):
                    dialogue.restore_dialogue(recipient)

                recipient_hidden_on_incoming = dialogue.should_hide_incoming_for_user(recipient)

        # Sender PoP.
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
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
    
    
    # -------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['post'],
        url_path='upload-file',
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_file(self, request):
        user = request.user
        dialogue_slug = request.data.get("dialogue_slug")
        uploaded_file = request.FILES.get("file")
        reply_to_message_id = request.data.get("reply_to_message_id")
        forwarded_from_message_id = request.data.get("forwarded_from_message_id")

        if not dialogue_slug:
            return Response(
                {"error": "Dialogue slug is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validation = validate_upload_input(uploaded_file=uploaded_file)
        if not validation.get("ok"):
            return Response(
                {"error": validation["message"], "code": validation["code"]},
                status=validation["status"],
            )

        validation_payload = validation["payload"]
        field_name = validation_payload["field_name"]
        file_type = validation_payload["file_type"]

        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=user)

        boundary_payload = private_dialogue_boundary_response_payload(
            dialogue=dialogue,
            acting_user=user,
        )

        if boundary_payload:
            return Response(
                boundary_payload,
                status=status.HTTP_403_FORBIDDEN,
            )
            
        # Validate forwarded source when iOS performs client-side media forwarding.
        forwarded_from_message = None

        if forwarded_from_message_id:
            try:
                forwarded_from_message = Message.objects.select_related(
                    "dialogue",
                    "sender",
                ).get(id=forwarded_from_message_id)
            except Message.DoesNotExist:
                return Response(
                    {
                        "error": "Forward source message not found.",
                        "code": "FORWARD_SOURCE_NOT_FOUND",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not forwarded_from_message.dialogue.participants.filter(id=user.id).exists():
                return Response(
                    {
                        "error": "You do not have access to the forward source message.",
                        "code": "FORWARD_SOURCE_FORBIDDEN",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if forwarded_from_message.deleted_by_users.filter(id=user.id).exists():
                return Response(
                    {
                        "error": "Forward source message is not visible to you.",
                        "code": "FORWARD_SOURCE_NOT_VISIBLE",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if forwarded_from_message.is_system:
                return Response(
                    {
                        "error": "System messages cannot be forwarded.",
                        "code": "INVALID_FORWARD_SOURCE",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Re-open dialogue on first outgoing file.
        dialogue.release_inbound_block_on_outgoing(user)

        recipient_hidden_on_incoming = False
        recipient = None

        if not dialogue.is_group:
            recipient = dialogue.participants.exclude(id=user.id).first()
            if recipient:
                if dialogue.should_restore_on_incoming_for_user(recipient):
                    dialogue.restore_dialogue(recipient)

                recipient_hidden_on_incoming = dialogue.should_hide_incoming_for_user(recipient)

        # Sender PoP.
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
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

        encrypted_prepare = prepare_encrypted_file_request(
            is_encrypted_file=str(request.data.get("is_encrypted_file", "")).strip().lower()
            in ("true", "1", "yes"),
            encrypted_for_device=request.data.get("encrypted_for_device"),
            aes_key_encrypted=request.data.get("aes_key_encrypted"),
            encrypted_keys_per_device=request.data.get("encrypted_keys_per_device"),
        )

        if not encrypted_prepare.get("ok"):
            return Response(
                {
                    "error": encrypted_prepare["message"],
                    "code": encrypted_prepare["code"],
                },
                status=encrypted_prepare["status"],
            )

        encrypted_payload = encrypted_prepare["payload"]

        result = create_file_message(
            dialogue=dialogue,
            sender=user,
            uploaded_file=uploaded_file,
            field_name=field_name,
            is_encrypted_file=encrypted_payload["is_encrypted_file"],
            encrypted_for_device=encrypted_payload["encrypted_for_device"],
            aes_key_encrypted_bytes=encrypted_payload["aes_key_encrypted_bytes"],
            encrypted_keys_per_device=encrypted_payload["encrypted_keys_per_device"],
            recipient_hidden_on_incoming=recipient_hidden_on_incoming,
            recipient=recipient,
            reply_to_message_id=reply_to_message_id,
            forwarded_from_message=forwarded_from_message,
        )

        if not result.get("ok"):
            return Response(
                {"error": result["message"], "code": result["code"]},
                status=result["status"],
            )

        payload = result["payload"]
        message = payload["message"]

        stored_file = getattr(message, field_name)
        file_key = getattr(stored_file, "name", None)
        file_url = get_file_url(file_key) if (file_key and not message.is_encrypted_file) else None

        return Response(
            {
                "file_url": file_url,
                "message_id": payload["message_id"],
                "file_type": file_type,
                "dialogue_slug": payload["dialogue_slug"],
                "is_encrypted_file": bool(message.is_encrypted_file),
                "websocket_url": get_websocket_url(request),
            },
            status=status.HTTP_201_CREATED,
        )

    # -------------------------------------------------------------------------------------------------
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

        # envelope برای دستگاه
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


    # Edit Message -----------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='edit-message', permission_classes=[IsAuthenticated])
    def edit_message(self, request, pk=None):
        try:
            logger.info(">> [EDIT] Starting edit_message for pk=%s user=%s", pk, request.user)

            message = get_object_or_404(
                Message.objects.select_related("dialogue", "sender"),
                pk=pk
            )
            dialogue = message.dialogue
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

            # Group edit -> broadcast one canonical group payload
            if payload["is_group"]:
                conv_group_send(
                    f"dialogue_{payload['dialogue_slug']}",
                    "edit_message",
                    build_group_edit_message_data(payload=payload),
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

        except Exception as e:
            logger.exception("‼️ ERROR DURING edit_message(): %s", e)
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

    # Mark As Delivered  -----------------------------------------------------------------------------------------
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

        conv_group_send(
            f"dialogue_{payload['dialogue_slug']}",
            "mark_as_delivered",
            realtime_data,
        )

        return Response(
            {"message": "Message marked as delivered."},
            status=status.HTTP_200_OK
        )
                

    # Mark As Read  --------------------------------------------------------------------------------------------
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
        realtime_data = build_mark_as_read_realtime_payload(payload)

        participant_ids = list(
            Dialogue.objects.get(slug=payload["dialogue_slug"], participants=user)
            .participants.exclude(id=user.id)
            .values_list("id", flat=True)
        )

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

    # Seen by -----------------------------------------------------------------------------------------
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

        # User must belong to the dialogue.
        if not dialogue.participants.filter(pk=user.pk).exists():
            return Response(
                {"error": "Access denied.", "code": "DIALOGUE_ACCESS_DENIED"},
                status=status.HTTP_403_FORBIDDEN,
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

    # Soft Delete Message ----------------------------------------------------------------------------------
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


    # Hard Delete Message ----------------------------------------------------------------------------------
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

    # Search Messages -----------------------------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="search-messages", permission_classes=[IsAuthenticated])
    def search_messages(self, request, pk=None):
        query = request.query_params.get("q")

        if not query:
            return Response({"error": "Search query `q` is required."}, status=400)

        dialogue = get_object_or_404(Dialogue, slug=pk)
        if not dialogue.participants.filter(id=request.user.id).exists():
            return Response({"error": "You are not a participant of this dialogue."}, status=403)

        if dialogue.is_group:
            matching_message_ids = (
                MessageSearchIndex.objects
                .filter(plaintext__icontains=query, message__dialogue=dialogue)
                .values_list("message_id", flat=True)
            )
            messages = (
                Message.objects
                .filter(id__in=matching_message_ids, is_system=False, dialogue=dialogue)
                .exclude(deleted_by_users=request.user)
                .order_by("-timestamp")[:100]
            )

            serializer = MessageSerializer(messages, many=True, context={"request": request})
            return Response(serializer.data)

        else:
            return Response({
                "note": "Client-side search is required for encrypted private chats.",
                "messages": []
            })


    # Get Message -------------------------------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="get-message", permission_classes=[IsAuthenticated])
    def get_message(self, request, pk=None):
        message = get_object_or_404(Message, pk=pk)

        if not message.dialogue.participants.filter(id=request.user.id).exists():
            return Response({"error": "Access denied."}, status=403)

        if message.deleted_by_users.filter(id=request.user.id).exists():
            return Response({"error": "Message not found."}, status=404)

        serializer = MessageSerializer(message, context={"request": request})
        return Response(serializer.data)

    # Pin Message -------------------------------------------------------------------------------------------
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

        for uid in dialogue.participants.values_list("id", flat=True):
            conv_group_send(
                f"user_{uid}",
                "message_pinned",
                realtime_data,
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

    # Unpin Message -----------------------------------------------------------------------------------------
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

        for uid in dialogue.participants.values_list("id", flat=True):
            conv_group_send(
                f"user_{uid}",
                "message_unpinned",
                realtime_data,
            )

        return Response(
            {
                "message": result["payload"]["result_message"],
            },
            status=status.HTTP_200_OK,
        )

    # Forward Message ----------------------------------------------------------------------------------------
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

    # Forward E2EE Text Message -------------------------------------------------------------------------------
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

    # Forward Decrypted Text To Group -------------------------------------------------------------------------
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
        
        
    # Toggle Message Reaction -------------------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="toggle-reaction", permission_classes=[IsAuthenticated])
    def toggle_reaction(self, request, pk=None):
        reaction_type = request.data.get("reaction_type")

        target_message = get_object_or_404(
            Message.objects.select_related("dialogue", "sender"),
            pk=pk,
        )

        if not target_message.dialogue.participants.filter(id=request.user.id).exists():
            return Response(
                {
                    "error": "Access denied.",
                    "code": "DIALOGUE_ACCESS_DENIED",
                },
                status=status.HTTP_403_FORBIDDEN,
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

        realtime_data = build_message_reaction_toggled_event_data(
            dialogue_slug=dialogue.slug,
            message_id=message.id,
            user_id=request.user.id,
            reaction_type=payload["reaction_type"],
            action=payload["action"],
            summary=summary,
        )

        # Shared dialogue state -> broadcast to all participants
        for uid in dialogue.participants.values_list("id", flat=True):
            conv_group_send(
                f"user_{uid}",
                "message_reaction_toggled",
                realtime_data,
            )

        return Response(
            {
                "message": "Reaction updated successfully.",
                "action": payload["action"],
                "summary": summary,
            },
            status=status.HTTP_200_OK,
        )

    # Message Reaction Summary ------------------------------------------------------------------------------
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

    # Message Reactors --------------------------------------------------------------------------------------
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
        

# USER DIALOGUE MARKER VIEWSET -------------------------------------------------------------------------
class UserDialogueMarkerViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def list(self, request):
        markers = UserDialogueMarker.objects.filter(user=request.user)
        serializer = UserDialogueMarkerSerializer(markers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-dialogue', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def mark_dialogue(self, request):
        dialogue_slug = request.data.get('dialogue_slug')
        is_sensitive = request.data.get('is_sensitive', False)
        delete_policy = request.data.get('delete_policy', 'SOFT_DELETE')

        if not dialogue_slug:
            return Response({'detail': 'Dialogue slug is required.'}, status=status.HTTP_400_BAD_REQUEST)

        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=request.user)
        marker, created = UserDialogueMarker.objects.get_or_create(
            user=request.user,
            dialogue=dialogue,
            defaults={'is_sensitive': is_sensitive, 'delete_policy': delete_policy}
        )

        if not created:
            marker.is_sensitive = is_sensitive
            marker.delete_policy = delete_policy
            marker.save()

        serializer = UserDialogueMarkerSerializer(marker)
        return Response(serializer.data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'], url_path='unmark-dialogue', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def unmark_dialogue(self, request, pk=None):
        marker = get_object_or_404(UserDialogueMarker, pk=pk, user=request.user)
        marker.delete()
        return Response({'detail': 'Dialogue unmarked as sensitive.'}, status=status.HTTP_204_NO_CONTENT)

