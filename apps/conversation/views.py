from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
import base64
import os
from django.db import transaction

        

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import asyncio
from services.redis_online_manager import get_last_seen, get_online_status_for_users
from datetime import datetime
from django.utils.timesince import timesince
from rest_framework.renderers import JSONRenderer
import json

from common.aws.s3_utils import get_file_url

from .models import Dialogue, Message, MessageSearchIndex, MessageEncryption, UserDialogueMarker, DialogueParticipant
from .serializers import DialogueSerializer, MessageSerializer, UserDialogueMarkerSerializer, DialogueParticipantSerializer, UpdateGroupInfoSerializer
from .permissions import ConversationAccessPermission, IsDialogueParticipant
from apps.accounts.services.sender_verification import is_sender_device_verified
from apps.accounts.serializers import SimpleCustomUserSerializer
from apps.accounts.models import UserDeviceKey
from apps.conversation.utils import get_websocket_url
from common.mime_type_validator import validate_file_type, is_unsafe_file
from apps.core.security.decorators import require_litshield_access


from django.contrib.auth import get_user_model
CustomUser = get_user_model()

def send_system_message(dialogue, sender, system_event, content):
    plain_text = content.strip()
    base64_str = base64.b64encode(plain_text.encode("utf-8")).decode("utf-8")
    content_bytes = base64_str.encode("utf-8")

    system_message = Message.objects.create(
        dialogue=dialogue,
        sender=sender,
        content_encrypted=content_bytes,
        is_system=True,
        system_event=system_event,
    )

    dialogue.last_message = system_message
    dialogue.save(update_fields=["last_message"])

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"dialogue_{dialogue.slug}",
        {
            "type": "chat_message",
            "event_type": "system_message",
            "dialogue_slug": dialogue.slug,
            "message_id": system_message.id,
            "content": base64_str,
            "sender": {
                "id": sender.id,
                "username": sender.username,
            },
            "timestamp": system_message.timestamp.isoformat(),
            "is_system": True,
            "system_event": system_event,
        }
    )


# DIALOGUE VIEWSET -------------------------------------------------------------------------
class DialogueViewSet(viewsets.ModelViewSet):
    queryset = Dialogue.objects.all()
    serializer_class = DialogueSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Dialogue.objects.filter(
            participants=self.request.user
        ).exclude(
            deleted_by_users=self.request.user
        ).prefetch_related('participants', 'participants_roles', 'marked_users')
        
    # ---------------------------------------
    @action(detail=False, methods=["post"], url_path="enter-chat")
    @require_litshield_access("conversation")
    def enter_chat(self, request):
        user = request.user
        device_id = request.data.get("device_id")

        dialogues = Dialogue.objects.filter(participants=user).exclude(deleted_by_users=user)
        serializer = DialogueSerializer(
            dialogues,
            many=True,
            context={"request": request, "device_id": device_id}
        )

        return Response({
            "dialogues": serializer.data
        }, status=status.HTTP_200_OK)
        
    # ---------------------------------------
    @action(detail=True, methods=["get"], url_path="keys", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def get_dialogue_keys(self, request, slug=None):
        dialogue = self.get_object()
        user = request.user
        if not dialogue.participants.filter(id=user.id).exists():
            return Response({"error": "Forbidden"}, status=403)

        partner = dialogue.participants.exclude(id=user.id).first()
        if not partner:
            return Response({"error": "No chat partner found."}, status=404)

        qs_verified = (UserDeviceKey.objects
                    .filter(user=partner, is_active=True, is_verified=True)
                    .only("device_id", "public_key")
                    .order_by("-last_used", "device_id"))

        qs_unverified = (UserDeviceKey.objects
                        .filter(user=partner, is_active=True, is_verified=False)
                        .only("device_id", "public_key")
                        .order_by("-last_used", "device_id"))

        full = request.query_params.get("full", "").lower() in ("1", "true", "yes")

        if full:
            return Response({
                "verified":   [{"device_id": k.device_id, "public_key": k.public_key} for k in qs_verified],
                "unverified": [{"device_id": k.device_id, "public_key": k.public_key} for k in qs_unverified],
            }, status=200)

        return Response([{"device_id": k.device_id, "public_key": k.public_key} for k in qs_verified], status=200)
        
    # ---------------------------------------   
    @action(detail=False, methods=['post'], url_path='create-dialogue', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def create_dialogue(self, request):
        recipient_id = request.data.get('recipient_id')
        check_only = request.data.get('check_only', False)

        if not recipient_id:
            return Response({'error': 'Recipient ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        recipient = get_object_or_404(CustomUser, id=recipient_id)

        # بررسی وجود دیالوگ
        dialogue = Dialogue.objects.filter(
            participants=request.user,
            is_group=False
        ).filter(participants=recipient).first()

        if dialogue:
            if dialogue.deleted_by_users.filter(id=request.user.id).exists():
                dialogue.deleted_by_users.remove(request.user)
            
            serializer = DialogueSerializer(dialogue, context={"request": request})
            return Response({
                'dialogue': serializer.data,
                'message': 'Dialogue already exists.'
            }, status=status.HTTP_200_OK)

        if check_only:
            return Response({
                'message': 'Dialogue does not exist.'
            }, status=status.HTTP_204_NO_CONTENT)

        # ایجاد دیالوگ جدید (در صورتی که check_only=False)
        dialogue = Dialogue.objects.create(is_group=False)
        dialogue.participants.add(request.user, recipient)

        usernames = sorted([request.user.username, recipient.username])
        dialogue.slug = Dialogue.generate_dialogue_slug(usernames)
        dialogue.save()

        DialogueParticipant.objects.create(dialogue=dialogue, user=request.user, role='participant')
        DialogueParticipant.objects.create(dialogue=dialogue, user=recipient, role='participant')

        serializer = DialogueSerializer(dialogue, context={"request": request})
        return Response({
            'dialogue': serializer.data,
            'message': 'New dialogue created.'
        }, status=status.HTTP_201_CREATED)


    # ---------------------------------------
    @action(detail=False, methods=['post'], url_path='create-group', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def create_group(self, request):
        data = request.data
        group_name = data.get('group_name')
        group_image = request.FILES.get('group_image')

        if not group_name:
            return Response({'error': 'Group name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if Dialogue.objects.filter(
            is_group=True,
            group_name__iexact=group_name.strip()
        ).exists():
            return Response({'error': 'A group with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        dialogue = Dialogue.objects.create(
            is_group=True,
            group_name=group_name.strip(),
            group_image=group_image,
        )

        # ✅ اضافه کردن موسس به لیست شرکت‌کنندگان
        dialogue.participants.add(request.user)
        DialogueParticipant.objects.create(dialogue=dialogue, user=request.user, role='founder')

        # ✅ ساخت slug با استفاده از نام گروه و نام موسس
        usernames = list(dialogue.participants.values_list("username", flat=True))
        dialogue.slug = Dialogue.generate_dialogue_slug(usernames, group_name)
        dialogue.save(update_fields=["slug"])
        serializer = DialogueSerializer(dialogue, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # Update Group Image Action ---------------
    @action(detail=True, methods=["post"], url_path="update-group-image", permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def update_group_image(self, request, **kwargs):
        dialogue = self.get_object()

        if not dialogue.is_group:
            return Response({"detail": "Only group dialogues can have images."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            participant = DialogueParticipant.objects.get(dialogue=dialogue, user=request.user)
            if participant.role not in ["founder", "elder"]:
                return Response({"detail": "You don't have permission to update the group image."}, status=status.HTTP_403_FORBIDDEN)
        except DialogueParticipant.DoesNotExist:
            return Response({"detail": "You are not a participant of this group."}, status=status.HTTP_404_NOT_FOUND)

        group_image = request.FILES.get("group_image")
        if not group_image:
            return Response({"detail": "No image uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        dialogue.group_image = group_image
        dialogue.save()

        return Response({"detail": "Group image updated successfully."}, status=status.HTTP_200_OK)

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
        user = request.user
        dialogue = get_object_or_404(Dialogue, slug=slug, participants=user)

        if not dialogue.is_group:
            dialogue.mark_as_deleted_by_user(user)
            
            for msg in dialogue.messages.all():
                msg.deleted_by_users.add(user)
                
            # Hard Delete if...
            other_participant = dialogue.participants.exclude(id=user.id).first()
            if other_participant and dialogue.deleted_by_users.filter(id=other_participant.id).exists():
                Message.objects.filter(dialogue=dialogue).delete()
                dialogue.delete()
                return Response({'message': 'Dialogue permanently deleted.'}, status=status.HTTP_200_OK)
            return Response({'message': 'Private chat deleted from your list.'}, status=status.HTTP_200_OK)

        participant = DialogueParticipant.objects.filter(dialogue=dialogue, user=user).first()
        if not participant:
            return Response({'error': 'You are not a participant of this group.'}, status=status.HTTP_403_FORBIDDEN)

        # Complitly Delete by Founder
        if participant.role == 'founder':
            Message.objects.filter(dialogue=dialogue).delete()
            DialogueParticipant.objects.filter(dialogue=dialogue).delete()
            dialogue.delete()
            return Response({'message': 'Group permanently deleted.'}, status=status.HTTP_200_OK)
        send_system_message(dialogue, request.user, 'group_deleted', "Group has been deleted by the founder.")
        return Response({'error': 'Only the founder can delete the group. To leave, use the leave action.'}, status=status.HTTP_403_FORBIDDEN)

    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='add-participant', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def add_participant(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        participant_id = request.data.get('participant_id')

        if not participant_id:
            return Response({'error': 'Participant ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        participant = get_object_or_404(CustomUser, pk=participant_id)
        current_user = request.user
        current_participant = DialogueParticipant.objects.filter(dialogue=dialogue, user=current_user).first()
        if not current_participant:
            return Response({'error': 'You are not a member of this group.'}, status=status.HTTP_403_FORBIDDEN)

        if current_participant.role not in ['founder', 'elder']:
            return Response({'error': 'Only founders or elders can add new participants.'}, status=status.HTTP_403_FORBIDDEN)

        if dialogue.participants.filter(id=participant.id).exists():
            return Response({'error': f'{participant.username} is already a member of the group.'}, status=status.HTTP_400_BAD_REQUEST)

        dialogue.participants.add(participant)
        DialogueParticipant.objects.get_or_create(
            dialogue=dialogue,
            user=participant,
            defaults={'role': 'participant'}
        )

        # Serialize with request user (current_user)
        serializer = DialogueSerializer(dialogue, context={"request": request})
        json_data = JSONRenderer().render(serializer.data)
        parsed_data = json.loads(json_data)
        parsed_data["my_role"] = "participant"

        # Send over WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{participant.id}",
            {
                "type": "group_added",
                "dialogue": parsed_data
            }
        )
        send_system_message(dialogue, request.user, 'joined', f"{participant.username} joined the group.")

        # Restore if previously deleted
        if dialogue.deleted_by_users.filter(id=participant.id).exists():
            dialogue.deleted_by_users.remove(participant)
    
        return Response({'message': f'{participant.username} added to the group.'}, status=status.HTTP_200_OK)

    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='remove-participant', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def remove_participant(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        participant_id = request.data.get('participant_id')

        if not participant_id:
            return Response({'error': 'Participant ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        participant = get_object_or_404(CustomUser, pk=participant_id)
        if not dialogue.is_group_manager(request.user):
            return Response({'error': 'You are not authorized to remove participants.'}, status=status.HTTP_403_FORBIDDEN)

        participant_role_obj = get_object_or_404(DialogueParticipant, dialogue=dialogue, user=participant)

        # If Founder...
        if participant_role_obj.role == 'founder':
            return Response({'error': 'Cannot remove the founder from the group.'}, status=status.HTTP_400_BAD_REQUEST)

        # If Elder...
        if participant_role_obj.role == 'elder':
            if not dialogue.has_multiple_elders():
                return Response({'error': 'Cannot remove the last elder from the group.'}, status=status.HTTP_400_BAD_REQUEST)

        participant_role_obj.delete()
        dialogue.participants.remove(participant)
        dialogue.mark_as_deleted_by_user(participant)
        for msg in dialogue.messages.all():
            msg.deleted_by_users.add(participant)
            
        channel_layer = get_channel_layer()
        serializer = DialogueSerializer(dialogue, context={"request": request})
        json_data = JSONRenderer().render(serializer.data)
        parsed_data = json.loads(json_data)
        async_to_sync(channel_layer.group_send)(
            f"user_{participant.id}",
            {
                "type": "group_removed",
                "dialogue": parsed_data
            }
        )                    
        send_system_message(dialogue, request.user, 'removed', f"{participant.username} was removed from the group.")
        return Response({'message': f'{participant.username} removed from the group.'}, status=status.HTTP_200_OK)

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

        if not dialogue.is_founder(request.user):
            return Response({'error': 'Only the founder can promote to elder.'}, status=403)

        participant = get_object_or_404(DialogueParticipant, dialogue=dialogue, user_id=user_id)
        participant.role = 'elder'
        participant.save()
        send_system_message(dialogue, request.user, 'promoted_to_elder', f"{participant.user.username} was promoted to Elder.")
        return Response({'message': 'User promoted to Elder.'}, status=200)

    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='demote-to-participant', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def demote_to_participant(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        user_id = request.data.get('user_id')

        if not user_id:
            return Response({'error': 'User ID is required.'}, status=400)

        if not dialogue.is_founder(request.user):
            return Response({'error': 'Only the founder can demote elders.'}, status=403)

        participant = get_object_or_404(DialogueParticipant, dialogue=dialogue, user_id=user_id)

        if participant.role != 'elder':
            return Response({'error': 'User is not an elder.'}, status=400)

        participant.role = 'participant'
        participant.save()
        send_system_message(dialogue, request.user, 'demoted_to_participant', f"{participant.user.username} was demoted to Participant.")
        return Response({'message': 'User demoted to Participant.'}, status=200)

    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='resign-elder-role', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def resign_elder_role(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)
        user = request.user

        try:
            participant = DialogueParticipant.objects.get(dialogue=dialogue, user=user)
        except DialogueParticipant.DoesNotExist:
            return Response({'error': 'You are not a participant of this group.'}, status=403)

        if participant.role != 'elder':
            return Response({'error': 'You are not an elder.'}, status=400)

        participant.role = 'participant'
        participant.save()
        send_system_message(dialogue, request.user, 'resigned_from_elder', f"{user.username} resigned from Elder role.")
        return Response({'message': 'You stepped down as an Elder.'}, status=200)

    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='leave-group', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation")
    def leave_group(self, request, slug=None):
        user = request.user
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)

        participant = DialogueParticipant.objects.filter(dialogue=dialogue, user=user).first()
        if not participant:
            return Response({'error': 'You are not a participant of this group.'}, status=status.HTTP_403_FORBIDDEN)

        if participant.role == 'founder':
            return Response({'error': 'Founders cannot leave the group. You must delete the group instead.'}, status=status.HTTP_403_FORBIDDEN)

        if participant.role == 'elder':
            return Response({'error': 'You must first resign from being an Elder before leaving the group.'}, status=status.HTTP_400_BAD_REQUEST)

        dialogue.leave_group(user)
        for msg in dialogue.messages.all():
            msg.deleted_by_users.add(user)

        # Send System Message
        send_system_message(dialogue, request.user, 'left', f"{user.username} left the group.")
    
        channel_layer = get_channel_layer()
        serialized_user = SimpleCustomUserSerializer(user, context={"request": request}).data

        for participant in dialogue.participants.exclude(id=user.id):
            async_to_sync(channel_layer.group_send)(
                f"user_{participant.id}",
                {
                    "type": "group_left",
                    "user": serialized_user,
                    "dialogue_slug": dialogue.slug,
                }
            )
    
        return Response({'message': 'You left the group and your chat was removed from the list.'}, status=status.HTTP_200_OK)

    # ---------------------------------------
    @action(detail=True, methods=['post'], url_path='transfer-founder', permission_classes=[IsAuthenticated])
    @require_litshield_access("conversation") 
    def transfer_founder(self, request, slug=None):
        dialogue = get_object_or_404(Dialogue, slug=slug, is_group=True)

        if not dialogue.is_founder(request.user):
            return Response({'error': 'Only founder can transfer founder role.'}, status=403)

        new_founder_id = request.data.get('user_id')
        if not new_founder_id:
            return Response({'error': 'New founder user_id is required.'}, status=400)

        new_founder = get_object_or_404(DialogueParticipant, dialogue=dialogue, user_id=new_founder_id)

        if new_founder.role != 'elder':
            return Response({'error': 'Only an Elder can be promoted to Founder.'}, status=400)

        # 👑 تغییر نقش‌ها
        old_founder = get_object_or_404(DialogueParticipant, dialogue=dialogue, user=request.user)
        old_founder.role = 'participant'
        old_founder.save()

        new_founder.role = 'founder'
        new_founder.save()
        
        channel_layer = get_channel_layer()
        for user in dialogue.participants.all():
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "founder_transferred",
                    "dialogue_slug": dialogue.slug,
                    "new_founder_id": new_founder.user.id,
                }
            )

        send_system_message(dialogue, request.user, 'founder_transferred', f"Founder role transferred to {new_founder.user.username}.")
        return Response({'message': 'Founder role transferred successfully. You have left the group.'}, status=200)

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
            print("❌ Error getting last seen:", e)

        return Response({
            'user_id': participant.id,
            'is_online': False,
            'last_seen': None,
            'last_seen_display': "Unknown"
        })


    # Get Unread Counts -------------------------
    @action(detail=False, methods=["get"], url_path="unread-counts", permission_classes=[IsAuthenticated])
    # @require_litshield_access("conversation")
    def get_unread_counts(self, request):
        user = request.user
        dialogues = Dialogue.objects.filter(participants=user)

        unread_data = []
        for dialogue in dialogues:
            unread_count = Message.objects.filter(
                dialogue=dialogue
            ).exclude(seen_by_users=user) \
            .exclude(sender=user)

            unread_data.append({
                "dialogue_slug": dialogue.slug,
                "unread_count": unread_count.count()
            })

        return Response(unread_data)


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

        messages_query = Message.objects.filter(dialogue=dialogue)\
            .exclude(deleted_by_users=request.user)\
            .order_by("-timestamp")

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
    @action( detail=False, methods=['post'], url_path='send-message', permission_classes=[IsAuthenticated], parser_classes=[JSONParser] )
    def send_message(self, request):
        user = request.user
        dialogue_slug = request.data.get("dialogue_slug")
        is_encrypted = bool(request.data.get("is_encrypted", False))
        encrypted_contents = request.data.get("encrypted_contents", [])

        # 1) Basic validation
        if not dialogue_slug:
            return Response({"error": "dialogue_slug is required."}, status=status.HTTP_400_BAD_REQUEST)

        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=user)

        # Un-delete if the user had deleted this dialogue
        if dialogue.deleted_by_users.filter(id=user.id).exists():
            dialogue.deleted_by_users.remove(user)

        # 2) Enforce sender PoP (only for DMs by default; configurable in settings)
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
        if not header_device:
            return Response({"error": "X-Device-ID header is required."}, status=status.HTTP_400_BAD_REQUEST)

        # NOTE: This enforces only for DMs if REQUIRE_SENDER_VERIFIED_DMS_ONLY=True (default).
        #       For groups it returns True unless you change settings to enforce globally.
        if not is_sender_device_verified(user, header_device, dialogue_is_group=bool(dialogue.is_group)):
            # Hard-block (recommended for DMs). Replace with logging if you want a soft rollout.
            return Response(
                {"error": "Sender device is not verified.", "code": "SENDER_DEVICE_UNVERIFIED"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3) Group vs DM handling
        if dialogue.is_group:
            # Group messages must NOT be encrypted (server-side stores base64-encoded bytes)
            if is_encrypted:
                return Response({"error": "Group messages should not be encrypted."}, status=status.HTTP_400_BAD_REQUEST)

            content = (request.data.get("content") or "").strip()
            if not content:
                return Response({"error": "Message content is required for group chat."}, status=status.HTTP_400_BAD_REQUEST)

            # Store as base64 bytes for uniformity with encrypted storage
            base64_str = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            content_bytes = base64_str.encode("utf-8")

            message = Message.objects.create(
                dialogue=dialogue,
                sender=user,
                content_encrypted=content_bytes,
            )

        else:
            # DM path: client-side E2EE is required
            if not is_encrypted:
                return Response({"error": "DM messages must be encrypted on client."}, status=status.HTTP_400_BAD_REQUEST)

            if not encrypted_contents or not isinstance(encrypted_contents, list):
                return Response({"error": "encrypted_contents must be a non-empty list."}, status=status.HTTP_400_BAD_REQUEST)

            # Create message shell first (content is placeholder)
            message = Message.objects.create(
                dialogue=dialogue,
                sender=user,
                content_encrypted=b"[Encrypted]",
            )

            # 4) Sanitize and dedupe encrypted_contents by device_id
            #    Keep the first occurrence per device_id (stable behavior)
            seen = set()
            to_create = []
            for enc in encrypted_contents:
                device_id = (enc.get("device_id") or "").strip().lower()
                encrypted_content = enc.get("encrypted_content")

                # Skip invalid entries
                if not device_id or not encrypted_content or not isinstance(encrypted_content, str):
                    continue
                if device_id in seen:
                    continue
                seen.add(device_id)

                to_create.append(
                    MessageEncryption(
                        message=message,
                        device_id=device_id,
                        encrypted_content=encrypted_content,
                    )
                )

            if not to_create:
                # If nothing valid remains, roll back message creation for cleanliness
                message.delete()
                return Response({"error": "No valid encrypted contents."}, status=status.HTTP_400_BAD_REQUEST)

            # (Optional) impose a safe upper bound to avoid abuse (e.g., 200 devices)
            MAX_PER_MESSAGE = 500
            if len(to_create) > MAX_PER_MESSAGE:
                to_create = to_create[:MAX_PER_MESSAGE]

            MessageEncryption.objects.bulk_create(to_create)

        # 5) Finalize dialogue metadata
        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

        return Response(
            {
                "dialogue_slug": dialogue.slug,
                "message_id": message.id,
                "websocket_url": get_websocket_url(request, dialogue.slug),
            },
            status=status.HTTP_201_CREATED,
        )

    # -------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='upload-file', permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser])
    def upload_file(self, request):
        user = request.user
        dialogue_slug = request.data.get("dialogue_slug")
        uploaded_file = request.FILES.get("file")

        # --- Basic validations -----------------------------------------------------
        if not dialogue_slug or not uploaded_file:
            return Response({"error": "Dialogue slug and file are required."}, status=status.HTTP_400_BAD_REQUEST)

        MAX_FILE_SIZE = 1000 * 1024 * 1024  # 1000 MB
        if uploaded_file.size > MAX_FILE_SIZE:
            return Response({"error": "File too large. Max size is 1000MB."}, status=status.HTTP_400_BAD_REQUEST)

        file_name = (uploaded_file.name or "").lower()
        file_type = uploaded_file.content_type or "application/octet-stream"

        if is_unsafe_file(file_name):
            return Response({"error": "This file type is not allowed for security reasons."}, status=status.HTTP_400_BAD_REQUEST)

        field_name = validate_file_type(file_name, file_type)
        if not field_name:
            return Response({"error": f"Unsupported file type: {file_type}"}, status=status.HTTP_400_BAD_REQUEST)

        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=user)

        # If user had deleted the dialogue, revive it on new activity
        if dialogue.deleted_by_users.filter(id=user.id).exists():
            dialogue.deleted_by_users.remove(user)

        # --- Sender PoP enforcement (DMs by default; groups bypass unless configured) ---
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
        if not header_device:
            return Response({"error": "X-Device-ID header is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not is_sender_device_verified(user, header_device, dialogue_is_group=bool(dialogue.is_group)):
            return Response(
                {"error": "Sender device is not verified.", "code": "SENDER_DEVICE_UNVERIFIED"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # --- E2EE flags & inputs ---------------------------------------------------
        is_encrypted_file = str(request.data.get("is_encrypted_file", "")).strip().lower() in ("true", "1", "yes")
        aes_key_encrypted_main = request.data.get("aes_key_encrypted")
        encrypted_for_device = (request.data.get("encrypted_for_device") or "").strip().lower()  # normalize

        # Policy: group messages must NOT be client-encrypted; DMs MUST be client-encrypted
        if dialogue.is_group and is_encrypted_file:
            return Response({"error": "Group files must not be client-encrypted."}, status=status.HTTP_400_BAD_REQUEST)
        if (not dialogue.is_group) and (not is_encrypted_file):
            return Response({"error": "DM file uploads must be end-to-end encrypted."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Case 1: Group OR non-encrypted file in general (only groups allowed here) ---
        if dialogue.is_group:
            message = Message.objects.create(
                dialogue=dialogue,
                sender=user,
                is_encrypted_file=False,
                **{field_name: uploaded_file},
            )

        # --- Case 2: DM + client-side E2EE file upload ----------------------------------
        else:
            # Basic required E2EE fields
            if not aes_key_encrypted_main or not encrypted_for_device:
                return Response({"error": "Missing E2EE fields: aes_key_encrypted and encrypted_for_device."}, status=status.HTTP_400_BAD_REQUEST)

            # Decode the main AES key (encrypted with recipient device's public key)
            try:
                aes_key_bytes = base64.b64decode(aes_key_encrypted_main.encode("utf-8"))
            except Exception:
                return Response({"error": "Invalid base64 for aes_key_encrypted."}, status=status.HTTP_400_BAD_REQUEST)

            message = Message.objects.create(
                dialogue=dialogue,
                sender=user,
                is_encrypted_file=True,
                encrypted_for_device=encrypted_for_device,  # normalized device_id
                aes_key_encrypted=aes_key_bytes,
                **{field_name: uploaded_file},
            )

            # Optional: per-device key envelopes (JSON dict: {device_id: encrypted_key})
            encrypted_keys_json = request.data.get("encrypted_keys_per_device")
            if encrypted_keys_json:
                try:
                    payload = json.loads(encrypted_keys_json)
                    if isinstance(payload, dict):
                        seen = set()
                        to_create = []
                        for dev_id, enc_key in payload.items():
                            did = (str(dev_id or "").strip().lower())
                            enc = enc_key if isinstance(enc_key, str) else None
                            if not did or not enc:
                                continue
                            if did in seen:
                                continue
                            seen.add(did)
                            to_create.append(
                                MessageEncryption(message=message, device_id=did, encrypted_content=enc)
                            )
                        if to_create:
                            # Optional upper bound
                            MAX_PER_MESSAGE = 500
                            MessageEncryption.objects.bulk_create(to_create[:MAX_PER_MESSAGE])
                except Exception as e:
                    # Non-fatal: we keep the message but report parsing error
                    print("❌ Failed to parse/store per-device keys:", e)

        # --- Finalize dialogue metadata --------------------------------------------
        dialogue.last_message = message
        dialogue.save(update_fields=["last_message"])

        # file_url = request.build_absolute_uri(getattr(message, field_name).url)
        stored_file = getattr(message, field_name)
        file_url = stored_file.url if not message.is_encrypted_file else None

        return Response(
            {
                "file_url": file_url,
                "message_id": message.id,
                "file_type": file_type,
                "dialogue_slug": dialogue.slug,
                "is_encrypted_file": bool(message.is_encrypted_file),
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

        # ساخت لینک امضاشده به encrypted object روی S3
        key = getattr(media_field, "name", None)
        if not key:
            return Response({"error": "Media key missing."}, status=status.HTTP_404_NOT_FOUND)

        # inline: بدون Content-Disposition
        # download: با Content-Disposition: attachment
        force_download = (mode == "download")
        signed_url = get_file_url(key=key, expires_in=None, force_download=force_download)

        return Response(
            {
                "download_url": signed_url,                 # points to ENCRYPTED bytes
                "encrypted_aes_key": enc_entry.encrypted_content,  # base64 envelope (aes_key+nonce encrypted)
                # optionally include mime/filename hints if ذخیره کرده‌ای
                # "filename": os.path.basename(key),
                # "mime": media_field.file.content_type if available
            },
            status=status.HTTP_200_OK
        )



    # Edit Message -----------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='edit-message', permission_classes=[IsAuthenticated])
    def edit_message(self, request, pk=None):
        # 1) Load & basic ownership check
        message = get_object_or_404(Message, pk=pk, sender=request.user)
        if not message.can_edit():
            return Response(
                {'error': 'You can only edit messages within 12 hours of sending.'},
                status=status.HTTP_403_FORBIDDEN
            )

        dialogue = message.dialogue
        is_group = bool(dialogue.is_group)

        # 2) Enforce sender PoP (DMs by default; configurable via settings)
        header_device = (request.headers.get("X-Device-ID") or "").strip().lower()
        if not header_device:
            return Response({"error": "X-Device-ID header is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not is_sender_device_verified(request.user, header_device, dialogue_is_group=is_group):
            return Response(
                {"error": "Sender device is not verified.", "code": "SENDER_DEVICE_UNVERIFIED"},
                status=status.HTTP_403_FORBIDDEN
            )

        encrypted_contents = request.data.get('encrypted_contents', [])
        new_content = None

        if is_group:
            # 3) Group: server-side storage (base64-encoded text); must NOT be client-encrypted
            new_content = (request.data.get("content") or "").strip()
            if not new_content:
                return Response({'error': 'Message content cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

            base64_str = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
            content_bytes = base64_str.encode("utf-8")

            message.content_encrypted = content_bytes
            message.edited_at = timezone.now()
            message.is_edited = True
            # Clear E2EE-specific fields on group messages (safety)
            message.encrypted_for_device = None
            message.aes_key_encrypted = None
            message.save(update_fields=["content_encrypted", "edited_at", "is_edited",
                                        "encrypted_for_device", "aes_key_encrypted"])
        else:
            # 4) DM: must be client-encrypted; replace per-device envelopes
            if not isinstance(encrypted_contents, list) or not encrypted_contents:
                return Response(
                    {'error': 'Missing or invalid encrypted_contents for private chat.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Remove old envelopes
            MessageEncryption.objects.filter(message=message).delete()

            # Placeholder content (DM bodies are not stored in plaintext)
            message.content_encrypted = b"[Encrypted]"
            message.edited_at = timezone.now()
            message.is_edited = True
            message.save(update_fields=["content_encrypted", "edited_at", "is_edited"])

            # Sanitize, dedupe by device_id (first occurrence wins), and create rows
            seen = set()
            to_create = []
            for enc in encrypted_contents:
                device_id = (enc.get('device_id') or '').strip().lower()
                encrypted_content = enc.get('encrypted_content')

                if not device_id or not isinstance(encrypted_content, str) or not encrypted_content:
                    continue
                if device_id in seen:
                    continue
                seen.add(device_id)

                to_create.append(
                    MessageEncryption(
                        message=message,
                        device_id=device_id,
                        encrypted_content=encrypted_content
                    )
                )

            if not to_create:
                # Roll back edit if nothing valid remains
                return Response({"error": "No valid encrypted contents."}, status=status.HTTP_400_BAD_REQUEST)

            # Optional guardrail to prevent abuse
            MAX_PER_MESSAGE = 500
            MessageEncryption.objects.bulk_create(to_create[:MAX_PER_MESSAGE])

        # 5) WebSocket notification (avoid relying on message.is_encrypted field)
        is_encrypted_flag = not is_group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"dialogue_{dialogue.slug}",
            {
                "type": "edit_message",
                "dialogue_slug": dialogue.slug,
                "edited_at": message.edited_at.isoformat(),
                "is_encrypted": is_encrypted_flag,  # derived from dialogue type
                "is_edited": bool(message.is_edited),
                "encrypted_contents": encrypted_contents if not is_group else None,
                "new_content": new_content if is_group else None,
            }
        )

        return Response({'message': 'Message edited successfully.'}, status=status.HTTP_200_OK)


        
    # Mark As Delivered  -----------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='mark-as-delivered')
    def mark_as_delivered(self, request):
        message_id = request.data.get("message_id")
        dialogue_slug = request.data.get("dialogue_slug")

        if not message_id or not dialogue_slug:
            return Response(
                {'error': 'message_id and dialogue_slug are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=request.user)
            message = get_object_or_404(Message, id=message_id, dialogue=dialogue)

            user = request.user
            if user not in dialogue.participants.all():
                return Response({'error': 'Not a participant.'}, status=status.HTTP_403_FORBIDDEN)

            if message.sender_id == user.id:
                return Response({'error': 'Sender cannot ack delivered.'}, status=status.HTTP_403_FORBIDDEN)

            if not message.is_delivered:
                message.is_delivered = True
                message.save(update_fields=["is_delivered"])

            # broadcast to sender
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{message.sender_id}",
                {
                    "type": "mark_as_delivered",
                    "dialogue_slug": dialogue.slug,
                    "message_id": message.id,
                    "user_id": user.id,
                }
            )

            # (optional) also to dialogue group
            async_to_sync(channel_layer.group_send)(
                f"dialogue_{dialogue.slug}",
                {
                    "type": "mark_as_delivered",
                    "dialogue_slug": dialogue.slug,
                    "message_id": message.id,
                    "user_id": user.id,
                }
            )

            return Response({'message': 'Message marked as delivered.'}, status=status.HTTP_200_OK)

        except Http404:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # Mark As Read  --------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='mark-as-read')
    def mark_as_read(self, request):
        message_ids = request.data.get("message_ids")
        dialogue_slug = request.data.get("dialogue_slug")

        if not isinstance(message_ids, list) or not dialogue_slug:
            return Response({'error': 'message_ids (list) and dialogue_slug are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        dialogue = get_object_or_404(Dialogue, slug=dialogue_slug, participants=user)
        messages = Message.objects.filter(id__in=message_ids, dialogue=dialogue)

        for msg in messages:
            if user != msg.sender and user not in msg.seen_by_users.all():
                msg.seen_by_users.add(user)

        return Response({'message': 'Messages marked as read.'}, status=status.HTTP_200_OK)

        
    @action(detail=True, methods=['get'], url_path='seen-by', permission_classes=[IsAuthenticated])
    def seen_by(self, request, pk=None):
        message = get_object_or_404(Message, pk=pk)

        user = request.user
        dialogue = message.dialogue

        # بررسی عضویت در گفتگو
        if user not in dialogue.participants.all():
            return Response({'error': 'Access denied.'}, status=403)

        # بررسی نقش: فقط Founder یا Elder مجاز به دیدن لیست دیده‌شده‌ها هستند
        is_founder = dialogue.is_founder(user)
        is_elder = dialogue.is_elder(user)

        if not (is_founder or is_elder):
            return Response({'error': 'Permission denied. You are not allowed to view this info.'}, status=403)

        seen_users = message.seen_by_users.all()
        serializer = SimpleCustomUserSerializer(seen_users, many=True, context={"request": request})
        return Response(serializer.data)


    # Soft Delete Message ----------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='soft-delete', permission_classes=[IsAuthenticated])
    def soft_delete_message(self, request, pk=None):
        message = get_object_or_404(Message, pk=pk)
        user = request.user

        if user in message.deleted_by_users.all():
            return Response({'error': 'Message already deleted from your chat.'}, status=status.HTTP_400_BAD_REQUEST)

        message.mark_as_deleted_by_user(user)
        return Response({'message': 'Message soft deleted successfully.'}, status=status.HTTP_200_OK)


    # Hard Delete Message ----------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='hard-delete', permission_classes=[IsAuthenticated])
    def hard_delete_message(self, request, pk=None):
        message = get_object_or_404(Message, pk=pk)
        user = request.user

        is_sender = message.sender == user
        is_unseen = not message.seen_by_users.exclude(id=message.sender.id).exists()
        is_group_manager = message.dialogue.is_group and message.dialogue.is_group_manager(user)

        if (is_sender and is_unseen) or is_group_manager:
            if message.image:
                message.image.delete(save=False)
            if message.video:
                message.video.delete(save=False)
            if message.audio:
                message.audio.delete(save=False)
            if message.file:
                message.file.delete(save=False)

            message.delete()
            return Response({'message': 'Message permanently deleted.'}, status=status.HTTP_200_OK)

        return Response({'error': 'You are not allowed to permanently delete this message.'}, status=status.HTTP_403_FORBIDDEN)
    

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
                .filter(id__in=matching_message_ids, is_system=False)
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

        serializer = MessageSerializer(message, context={"request": request})
        return Response(serializer.data)






# USER DIALOGUE MARKER VIEWSET -------------------------------------------------------------------------
class UserDialogueMarkerViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, ConversationAccessPermission]

    def list(self, request):
        markers = UserDialogueMarker.objects.filter(user=request.user)
        serializer = UserDialogueMarkerSerializer(markers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-dialogue', permission_classes=[IsAuthenticated])
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
    def unmark_dialogue(self, request, pk=None):
        marker = get_object_or_404(UserDialogueMarker, pk=pk, user=request.user)
        marker.delete()
        return Response({'detail': 'Dialogue unmarked as sensitive.'}, status=status.HTTP_204_NO_CONTENT)

