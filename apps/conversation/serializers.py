from rest_framework import serializers
from .models import Dialogue, DialogueParticipant, DialogueKey, Message, UserDialogueMarker, MessageEncryption
from apps.conversation.utils import get_websocket_url
from apps.accounts.serializers import SimpleCustomUserSerializer
from apps.accounts.models import UserDeviceKey
from django.conf import settings
import base64


# Dialogue Participant Serializer ------------------------------------------------------
class DialogueParticipantSerializer(serializers.ModelSerializer):
    user = SimpleCustomUserSerializer(read_only=True)

    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = DialogueParticipant
        fields = ['user', 'role', 'role_display']
        read_only_fields = ['role_display']



# Dialogue Key Serializer --------------------------------------------------------------
class DialogueKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = DialogueKey
        fields = ['user', 'public_key', 'last_updated']


# Dialogue Serializer ------------------------------------------------------------------
class DialogueSerializer(serializers.ModelSerializer):
    participants = serializers.StringRelatedField(many=True)
    chat_partner = serializers.SerializerMethodField()     
    last_message = serializers.SerializerMethodField()
    participants_roles = DialogueParticipantSerializer(many=True, read_only=True)
    keys = DialogueKeySerializer(many=True, read_only=True)

    # Dynamically determine if any message in this dialogue is encrypted
    is_encrypted = serializers.SerializerMethodField()
    websocket_url = serializers.SerializerMethodField()
    group_image = serializers.ImageField(required=False, allow_null=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Dialogue
        fields = [
            'id', 'name', 'group_image', 'participants', 'chat_partner', 'created_at', 'is_group', 'last_message',
            'participants_roles', 'keys', 'is_encrypted', 'websocket_url', 'my_role'
        ]

    def get_websocket_url(self, obj):
        request = self.context.get('request')
        if request:
            return get_websocket_url(request, obj.id)
        return None

    def get_is_encrypted(self, obj):
        return obj.messages.filter(is_encrypted=True).exists()
    
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
        device_id = request.query_params.get("device_id") if request else None
        last_msg = obj.messages.filter(is_system=False).order_by("-timestamp").first()

        if last_msg:
            serializer = MessageSerializer(
                last_msg,
                context={"request": request, "device_id": device_id}
            )
            return serializer.data
        return None

    def get_group_image(self, obj):
        request = self.context.get('request')
        if obj.group_image:
            return request.build_absolute_uri(obj.group_image.url) if request else obj.group_image.url
        else:
            return request.build_absolute_uri('/media/sample/group-image.png') if request else 'media/sample/group-image.png'
        
    def get_my_role(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
            role_obj = obj.participants_roles.filter(user=user).first()
            return role_obj.role if role_obj else None
        return None
        

# Message Serializer -------------------------------------------------------------------
class MessageSerializer(serializers.ModelSerializer):
    sender = SimpleCustomUserSerializer(read_only=True)

    content_encrypted = serializers.SerializerMethodField()
    aes_key_encrypted = serializers.SerializerMethodField()
    encrypted_for_device = serializers.SerializerMethodField()

    image_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'dialogue', 'sender', 'timestamp', 'edited_at', 'is_edited',
            'seen_by_users', 'is_delivered',
            'content_encrypted', 'aes_key_encrypted', 'encrypted_for_device',
            'image', 'video', 'file', 'audio',
            'image_url', 'video_url', 'file_url', 'audio_url',
            'is_system', 'system_event',
            'self_destruct_at', 'is_encrypted', 'is_encrypted_file',
        ]
        extra_kwargs = {
            'sender': {'read_only': True},
            'timestamp': {'read_only': True},
            'is_encrypted': {'read_only': True},
        }
            
    def get_content_encrypted(self, obj):
        request = self.context.get("request")
        device_id = self.context.get("device_id") or (request.query_params.get("device_id") if request else None)

        if not obj.is_encrypted:
            if obj.content_encrypted:
                try:
                    # ✅ تبدیل Binary → UTF-8 (اگر پیام گروهی باشد)
                    return base64.b64decode(obj.content_encrypted).decode("utf-8")
                except Exception as e:
                    return "⚠️ Failed to decode content"
            return None

        # پیام رمزنگاری شده:
        if not device_id:
            return None

        encryption = obj.encryptions.filter(device_id=device_id).first()
        if encryption:
            return encryption.encrypted_content
        else:
            return base64.b64encode(b"[Encrypted]").decode("utf-8")

    def get_encrypted_for_device(self, obj):
        return self.context.get("device_id")

    def get_aes_key_encrypted(self, obj):
        return base64.b64encode(obj.aes_key_encrypted).decode('utf-8') if obj.aes_key_encrypted else None

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None

    def get_video_url(self, obj):
        return obj.video.url if obj.video else None

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None

    def get_audio_url(self, obj):
        return obj.audio.url if obj.audio else None




# User Dialogue Marker Serializer -----------------------------------------------------
class UserDialogueMarkerSerializer(serializers.ModelSerializer):
    dialogue_id = serializers.IntegerField(source='dialogue.id', read_only=True)

    class Meta:
        model = UserDialogueMarker
        fields = ['id', 'user', 'dialogue_id', 'is_sensitive', 'delete_policy']
