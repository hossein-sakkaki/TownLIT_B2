from rest_framework import serializers
from common.file_handlers.group_image import GroupImageMixin
import base64
from django.db.models import Count

from .models import Dialogue, DialogueParticipant, Message, UserDialogueMarker
from apps.accounts.serializers import SimpleCustomUserSerializer
from apps.accounts.models import UserDeviceKey
from apps.conversation.utils import get_websocket_url
from common.aws.s3_utils import get_file_url


# Dialogue Participant Serializer ------------------------------------------------------
class DialogueParticipantSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)

    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = DialogueParticipant
        fields = ['user', 'role', 'role_display']
        read_only_fields = ['role_display']


# Dialogue Serializer ------------------------------------------------------------------
class DialogueSerializer(GroupImageMixin, serializers.ModelSerializer):
    participants = SimpleCustomUserSerializer(many=True, read_only=True)
    
    chat_partner = serializers.SerializerMethodField()     
    last_message = serializers.SerializerMethodField()
    participants_roles = DialogueParticipantSerializer(many=True, read_only=True)

    # Dynamically determine if any message in this dialogue is encrypted
    is_encrypted = serializers.SerializerMethodField()
    websocket_url = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    is_sensitive = serializers.SerializerMethodField()
    marker_id = serializers.SerializerMethodField()

    class Meta:
        model = Dialogue
        fields = [
            'id', 'slug', 'group_name', 'participants', 'chat_partner', 'created_at', 'is_group', 'last_message',
            'participants_roles', 'is_encrypted', 'websocket_url', 'my_role',
            'is_sensitive', 'marker_id'
        ]

    def get_websocket_url(self, obj):
        request = self.context.get('request')
        if request:
            return get_websocket_url(request, obj.slug)
        return None

    def get_is_encrypted(self, obj):
        return obj.messages.annotate(enc_count=Count("encryptions")).filter(enc_count__gt=0).exists()
        
    def get_chat_partner(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        
        other_participants = obj.participants.exclude(id=request.user.id)
        if not other_participants.exists():
            return None
        
        user = other_participants.first()
        user_data = SimpleCustomUserSerializer(user, context=self.context).data
        active_key = UserDeviceKey.objects.filter(user=user, is_active=True).order_by('-last_used').first()
        if active_key:
            user_data["public_key"] = active_key.public_key
            user_data["device_id"] = active_key.device_id
        else:
            user_data["public_key"] = None
            user_data["device_id"] = None

        return user_data


    def get_last_message(self, obj):
        request = self.context.get("request")
        device_id = request.query_params.get("device_id", "").strip().lower() if request else None
        last_msg = obj.messages.filter(is_system=False).order_by("-timestamp").first()

        if last_msg:
            serializer = MessageSerializer(
                last_msg,
                context={"request": request, "device_id": device_id}
            )
            return serializer.data
        return None
        
    def get_my_role(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
            role_obj = obj.participants_roles.filter(user=user).first()
            return role_obj.role if role_obj else None
        return None

    def get_is_sensitive(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        marker = obj.marked_users.filter(user=request.user).first()
        return marker.is_sensitive if marker else False

    def get_marker_id(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        marker = obj.marked_users.filter(user=request.user).first()
        return marker.id if marker else None


# Update Group Info Serializer --------------------------------------------------------
class UpdateGroupInfoSerializer(serializers.Serializer):
    group_name = serializers.CharField(required=False, allow_blank=False, max_length=64, trim_whitespace=True)
    # info = serializers.CharField(required=False, allow_blank=True, max_length=512, trim_whitespace=True)
    # bio = serializers.CharField(required=False, allow_blank=True, max_length=2048, trim_whitespace=True)

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

    class Meta:
        model = Message
        fields = [
            'id', 'dialogue', 'sender', 'timestamp', 'edited_at', 'is_edited',
            'seen_by_users', 'seen_count', 'seen_count_others', 'is_delivered',
            'content_encrypted', 'aes_key_encrypted', 'encrypted_for_device',
            'image', 'video', 'file', 'audio',
            'image_url','image_download_url',
            'video_url','video_download_url',
            'file_url','file_download_url',
            'audio_url','audio_download_url',
            'is_system', 'system_event',
            'self_destruct_at', 'is_encrypted', 'is_encrypted_file',
            
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
        device_id = self.context.get("device_id") or (request.query_params.get("device_id") if request else None)

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
        return self.context.get("device_id")

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

    # ---- getters (فقط برای غیررمز)
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

    # --- Seen counters ---
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

# User Dialogue Marker Serializer -----------------------------------------------------
class UserDialogueMarkerSerializer(serializers.ModelSerializer):
    dialogue_id = serializers.IntegerField(source='dialogue.id', read_only=True)

    class Meta:
        model = UserDialogueMarker
        fields = ['id', 'user', 'dialogue_id', 'is_sensitive', 'delete_policy']
