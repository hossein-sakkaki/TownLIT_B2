# apps/conversation/serializers.py

from rest_framework import serializers
import base64
from django.db.models import Count
from rest_framework.reverse import reverse

from .models import Dialogue, DialogueParticipant, Message, UserDialogueMarker, DialoguePin, MessagePin, MessageReaction
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.mixins import GroupAvatarURLMixin
from apps.accounts.models.devices import UserDeviceKey
from apps.conversation.utils import get_websocket_url
from common.aws.s3_utils import get_file_url
from apps.conversation.services.message_reply import build_reply_preview
from apps.conversation.services.message_forward import build_forward_preview
from apps.conversation.services.message_reactions import build_message_reaction_summary
from django.core.exceptions import ValidationError as DjangoValidationError
from validators.groupNames.group_name_validator import validate_group_name
from apps.conversation.services.boundary_access import check_private_dialogue_boundary
from apps.core.boundaries.serializers import boundary_unavailable_reason_to_text
from apps.conversation.services.message_media_descriptors import (
    build_message_media_descriptor,
)


# Dialogue Participant Serializer ------------------------------------------------------
class DialogueParticipantSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)

    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = DialogueParticipant
        fields = ['user', 'role', 'role_display']
        read_only_fields = ['role_display']


# Dialogue Serializer ------------------------------------------------------------------
class DialogueSerializer(GroupAvatarURLMixin, serializers.ModelSerializer):
    """
    Serializer for 1:1 and group dialogues.
    - For participants: uses SimpleCustomUserSerializer (with avatar_url).
    - For groups: exposes group_avatar_url as a proxy endpoint (no S3 on FE).
    """

    participants = SimpleCustomUserSerializer(many=True, read_only=True)

    chat_partner = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    participants_roles = DialogueParticipantSerializer(many=True, read_only=True)

    is_encrypted = serializers.SerializerMethodField()
    websocket_url = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    is_sensitive = serializers.SerializerMethodField()
    marker_id = serializers.SerializerMethodField()

    # NEW: group avatar proxy URL (for group chats)
    group_avatar_url = serializers.SerializerMethodField()
    group_avatar_cdn_url = serializers.SerializerMethodField()
    group_avatar_version = serializers.IntegerField(read_only=True)
    
    is_pinned = serializers.SerializerMethodField()
    pinned_position = serializers.IntegerField(read_only=True, allow_null=True)

    direct_interaction_available = serializers.SerializerMethodField()
    direct_interaction_unavailable_reason = serializers.SerializerMethodField()
    
    class Meta:
        model = Dialogue
        fields = [
            "id",
            "slug",
            "group_name",
            "participants",
            "chat_partner",
            "created_at",
            "is_group",
            "last_message",
            "participants_roles",
            "is_encrypted",
            "websocket_url",
            "my_role",
            "is_sensitive",
            "marker_id",
            
            "group_avatar_url", "group_avatar_cdn_url", "group_avatar_version",
            
            "is_pinned", "pinned_position",
            
            "direct_interaction_available",
            "direct_interaction_unavailable_reason",
        ]

    # -------------------------------------------------------------------
    # WebSocket URL
    # -------------------------------------------------------------------
    def get_websocket_url(self, obj):
        request = self.context.get("request")
        if request:
            return get_websocket_url(request)
        return None

    # -------------------------------------------------------------------
    # Encryption flag
    # -------------------------------------------------------------------
    def get_is_encrypted(self, obj):
        # True if any message in this dialogue has encryptions
        return (
            obj.messages
            .annotate(enc_count=Count("encryptions"))
            .filter(enc_count__gt=0)
            .exists()
        )

    # -------------------------------------------------------------------
    # Chat partner (for 1:1)
    # -------------------------------------------------------------------
    def get_chat_partner(self, obj):
        """
        For 1:1 dialogues: return the "other" participant with avatar_url & key info.
        For group dialogues: usually None (frontend shows group info instead).
        """
        request = self.context.get("request")
        if not request:
            return None

        if obj.is_group:
            # For groups you normally don't expose a single partner
            return None

        other_participants = obj.participants.exclude(id=request.user.id)
        if not other_participants.exists():
            return None

        user = other_participants.first()

        user_data = SimpleCustomUserSerializer(
            user,
            context=self.context,
        ).data

        # Attach latest active device public key (if any)
        active_key = (
            UserDeviceKey.objects
            .filter(user=user, is_active=True)
            .order_by("-last_used")
            .first()
        )
        if active_key:
            user_data["public_key"] = active_key.public_key
            user_data["device_id"] = active_key.device_id
        else:
            user_data["public_key"] = None
            user_data["device_id"] = None

        return user_data

    # -------------------------------------------------------------------
    # Direct interaction availability
    # -------------------------------------------------------------------
    def _direct_interaction_check(self, obj):
        request = self.context.get("request")

        if not request or not hasattr(request, "user"):
            return None

        # Group membership/history stays available.
        # Boundary only blocks direct/private interaction.
        if obj.is_group:
            return None

        return check_private_dialogue_boundary(
            dialogue=obj,
            acting_user=request.user,
        )

    def get_direct_interaction_available(self, obj):
        check = self._direct_interaction_check(obj)

        if check is None:
            return True

        return bool(check.allowed)

    def get_direct_interaction_unavailable_reason(self, obj):
        check = self._direct_interaction_check(obj)

        if check is None or check.allowed:
            return None

        return boundary_unavailable_reason_to_text(
            {
                "code": getattr(check, "code", None),
                "message": getattr(check, "message", None),
                "counterpart_id": getattr(check, "counterpart_id", None),
            },
            fallback=getattr(check, "message", None),
        )
        
    # -------------------------------------------------------------------
    # Last message
    # -------------------------------------------------------------------
    def get_last_message(self, obj):
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return None

        device_id = (
            request.query_params.get("device_id", "")
            or request.headers.get("X-Device-ID", "")
        ).strip().lower()

        last_msg = obj.get_last_message_for_user(request.user)
        if not last_msg:
            return None

        serializer = MessageSerializer(
            last_msg,
            context={"request": request, "device_id": device_id},
        )
        return serializer.data
    
    # -------------------------------------------------------------------
    # My role in this dialogue
    # -------------------------------------------------------------------
    def get_my_role(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
            role_obj = obj.participants_roles.filter(user=user).first()
            return role_obj.role if role_obj else None
        return None

    # -------------------------------------------------------------------
    # Sensitivity + marker
    # -------------------------------------------------------------------
    def get_is_sensitive(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        marker = obj.marked_users.filter(user=request.user).first()
        return marker.is_sensitive if marker else False

    def get_marker_id(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        marker = obj.marked_users.filter(user=request.user).first()
        return marker.id if marker else None

    # -------------------------------------------------------------------
    # Group Avatar
    # -------------------------------------------------------------------
    def get_group_avatar_cdn_url(self, obj):
        return GroupAvatarURLMixin.get_group_avatar_cdn_url(self, obj)

    # -------------------------------------------------------------------
    # Pin state
    # -------------------------------------------------------------------
    def get_is_pinned(self, obj):
        annotated_position = getattr(obj, "pinned_position", None)
        if annotated_position is not None:
            return True

        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return False

        return DialoguePin.objects.filter(
            user=request.user,
            dialogue=obj,
        ).exists()


# Create Group Serializer ---------------------------------------------------------------
class CreateGroupSerializer(serializers.Serializer):
    group_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=60,
        trim_whitespace=True,
    )
    group_image = serializers.ImageField(
        required=False,
        allow_null=True,
    )

    def validate_group_name(self, value):
        try:
            return validate_group_name(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0])
        
        
# Update Group Info Serializer --------------------------------------------------------
class UpdateGroupInfoSerializer(serializers.Serializer):
    group_name = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=60,
        trim_whitespace=True,
    )

    def validate_group_name(self, value):
        try:
            return validate_group_name(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0])

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs


# Message Serializer -------------------------------------------------------------------
class MessageSerializer(serializers.ModelSerializer):
    sender = SimpleCustomUserSerializer(read_only=True)
    content_encrypted = serializers.SerializerMethodField()
    aes_key_encrypted = serializers.SerializerMethodField()
    encrypted_for_device = serializers.SerializerMethodField()
    is_encrypted = serializers.SerializerMethodField()
    
    seen_count = serializers.SerializerMethodField()
    seen_count_others = serializers.SerializerMethodField()

    image_url = serializers.SerializerMethodField()
    image_download_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    video_download_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    audio_download_url = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_download_url = serializers.SerializerMethodField()
    
    image_media = serializers.SerializerMethodField()
    video_media = serializers.SerializerMethodField()
    audio_media = serializers.SerializerMethodField()
    file_media = serializers.SerializerMethodField()
    
    is_pinned = serializers.SerializerMethodField()
    pinned_position = serializers.SerializerMethodField()

    reply_to_message_id = serializers.IntegerField(source="reply_to_id", read_only=True)
    reply_preview = serializers.SerializerMethodField()

    is_forwarded = serializers.BooleanField(read_only=True)
    forwarded_from_message_id = serializers.IntegerField(source="forwarded_from_id", read_only=True, allow_null=True)
    forward_preview = serializers.SerializerMethodField()
    
    reaction_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'dialogue', 'sender', 'timestamp', 'edited_at', 'is_edited',
            'seen_by_users', 'seen_count', 'seen_count_others', 'is_delivered',
            'reply_to_message_id', 'reply_preview',
            'is_forwarded', 'forwarded_from_message_id', 'forward_preview',
            'reaction_summary',
            'content_encrypted', 'aes_key_encrypted', 'encrypted_for_device',
            'image', 'video', 'file', 'audio',
            'image_url','image_download_url',
            'video_url','video_download_url',
            'file_url','file_download_url',
            'audio_url','audio_download_url',
             'image_media', 'video_media', 'audio_media', 'file_media',
            'is_system', 'system_event',
            'self_destruct_at', 'is_encrypted', 'is_encrypted_file',
            'is_pinned', 'pinned_position',
        ]
        extra_kwargs = {
            'sender': {'read_only': True},
            'timestamp': {'read_only': True},
        }
        

    def get_is_encrypted(self, obj):
        return obj.is_encrypted 

    def get_content_encrypted(self, obj):
        """
        Returns per-device encrypted payload for the requesting device_id.
        Fallback: if not found for current device_id, try any of the user's registered device_ids.
        This helps after localStorage reset + restore (new device_id) so old messages remain decryptable.
        """
        request = self.context.get("request")
        device_id = (
            self.context.get("device_id")
            or (request.query_params.get("device_id") if request else None)
            or (request.headers.get("X-Device-ID") if request else None)
        )

        if device_id:
            device_id = device_id.strip().lower()  # Normalize

        # Unencrypted / group message: decode server-stored Base64 string back to UTF-8
        if not obj.is_encrypted:
            if obj.content_encrypted:
                try:
                    return base64.b64decode(obj.content_encrypted).decode("utf-8")
                except Exception:
                    return "⚠️ Failed to decode content"
            return None

        # Encrypted (private) message requires a device_id
        if not device_id:
            return None

        # 1) Try exact match for current device_id
        encryption = obj.encryptions.filter(device_id=device_id).first()
        if encryption:
            return encryption.encrypted_content

        # 2) Fallback: try any of this user's registered device_ids
        user = request.user if request else None
        if user and user.is_authenticated:
            # Collect all device_ids registered for this user
            user_device_ids = list(UserDeviceKey.objects.filter(user=user).values_list("device_id", flat=True))
            if user_device_ids:
                fallback_enc = obj.encryptions.filter(device_id__in=user_device_ids).first()
                if fallback_enc:
                    return fallback_enc.encrypted_content

        # Nothing found for this device nor any of the user's devices
        return None  # keep previous behavior; alternatively, return base64.b64encode(b"[Encrypted]").decode("utf-8")


    def get_encrypted_for_device(self, obj):
        request = self.context.get("request")
        device_id = (
            self.context.get("device_id")
            or (request.query_params.get("device_id") if request else None)
            or (request.headers.get("X-Device-ID") if request else None)
        )
        return device_id.strip().lower() if device_id else None

    def get_aes_key_encrypted(self, obj):
        return base64.b64encode(obj.aes_key_encrypted).decode('utf-8') if obj.aes_key_encrypted else None


    # ---- helpers
    def _inline_url(self, field):
        if not field:
            return None
        return get_file_url(getattr(field, 'name', None))

    def _download_url(self, field):
        if not field:
            return None
        return get_file_url(getattr(field, 'name', None), force_download=True)

    # ---- getters for file URLs
    def _maybe(self, obj, field_name, download=False):
        if obj.is_encrypted_file:  # DM/E2EE → URL نده
            return None
        field = getattr(obj, field_name, None)
        return self._download_url(field) if download else self._inline_url(field)

    def get_image_url(self, obj):            return self._maybe(obj, 'image', download=False)
    def get_image_download_url(self, obj):   return self._maybe(obj, 'image', download=True)
    def get_video_url(self, obj):            return self._maybe(obj, 'video', download=False)
    def get_video_download_url(self, obj):   return self._maybe(obj, 'video', download=True)
    def get_audio_url(self, obj):            return self._maybe(obj, 'audio', download=False)
    def get_audio_download_url(self, obj):   return self._maybe(obj, 'audio', download=True)
    def get_file_url(self, obj):             return self._maybe(obj, 'file', download=False)
    def get_file_download_url(self, obj):    return self._maybe(obj, 'file', download=True)

    # ---- media descriptors
    def get_image_media(self, obj):
        return build_message_media_descriptor(obj, "image", "image")

    def get_video_media(self, obj):
        return build_message_media_descriptor(obj, "video", "video")

    def get_audio_media(self, obj):
        return build_message_media_descriptor(obj, "audio", "audio")

    def get_file_media(self, obj):
        return build_message_media_descriptor(obj, "file", "file")
    
    #  Seen counters ----------------------------------
    def get_seen_count(self, obj):
        """Number of viewers excluding the sender."""
        return obj.seen_by_users.exclude(pk=obj.sender_id).count()

    def get_seen_count_others(self, obj):
        """
        Number of viewers excluding both the sender and the requesting user.
        Useful for "Seen by N" in the current user's UI.
        """
        request = self.context.get("request")
        qs = obj.seen_by_users.exclude(pk=obj.sender_id)
        if request and request.user and request.user.is_authenticated:
            qs = qs.exclude(pk=request.user.pk)
        return qs.count()

    # Pin state --------------------------------------
    def get_is_pinned(self, obj):
        return obj.pins.exists()

    def get_pinned_position(self, obj):
        pin = obj.pins.order_by("position", "created_at", "id").first()
        return pin.position if pin else None
    
    # Reply preview ----------------------------------
    def get_reply_preview(self, obj):
        request = self.context.get("request")
        acting_user = request.user if request and hasattr(request, "user") else None
        return build_reply_preview(message=obj, acting_user=acting_user)
    
    # Forward preview --------------------------------
    def get_forward_preview(self, obj):
        return build_forward_preview(message=obj)

    # Reaction summary -------------------------------
    def get_reaction_summary(self, obj):
        
        request = self.context.get("request")
        acting_user = request.user if request and hasattr(request, "user") else None
        return build_message_reaction_summary(message=obj, acting_user=acting_user)
    
    
# User Dialogue Marker Serializer -----------------------------------------------------
class UserDialogueMarkerSerializer(serializers.ModelSerializer):
    dialogue_id = serializers.IntegerField(source='dialogue.id', read_only=True)
    dialogue_slug = serializers.CharField(source='dialogue.slug', read_only=True)

    class Meta:
        model = UserDialogueMarker
        fields = ['id', 'user', 'dialogue_id', 'dialogue_slug', 'is_sensitive', 'delete_policy']


# Dialogue Pin Serializer ------------------------------------------------------------
class DialoguePinSerializer(serializers.ModelSerializer):
    dialogue = serializers.SerializerMethodField()

    class Meta:
        model = DialoguePin
        fields = ["id", "position", "pinned_at", "dialogue"]

    def get_dialogue(self, obj):
        serializer = DialogueSerializer(
            obj.dialogue,
            context=self.context,
        )
        return serializer.data
    
    
# Message Pin Serializer ------------------------------------------------------
class MessagePinSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()
    pinned_by = SimpleCustomUserSerializer(read_only=True)

    class Meta:
        model = MessagePin
        fields = [
            "id",
            "position",
            "pin_duration",
            "expires_at",
            "reminders_enabled",
            "next_reminder_at",
            "last_reminded_at",
            "created_at",
            "pinned_by",
            "message",
        ]

    def get_message(self, obj):
        request = self.context.get("request")
        device_id = (
            self.context.get("device_id")
            or (request.query_params.get("device_id") if request else None)
            or (request.headers.get("X-Device-ID") if request else None)
        )

        serializer = MessageSerializer(
            obj.message,
            context={"request": request, "device_id": device_id},
        )
        return serializer.data
    

# Message Reaction Serializer ------------------------------------------------------
class MessageReactionSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)

    class Meta:
        model = MessageReaction
        fields = [
            "id",
            "reaction_type",
            "created_at",
            "updated_at",
            "user",
        ]