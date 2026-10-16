# apps/conversation/serializers/message.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-15.
#

import base64

from rest_framework import serializers

from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.models import Message
from apps.conversation.policies import (
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.services.message_forward import build_forward_preview
from apps.conversation.services.message_media_descriptors import (
    build_message_media_descriptor,
)
from apps.conversation.services.message_reactions import (
    build_message_reaction_summary,
)
from apps.conversation.services.message_reply import build_reply_preview
from common.aws.s3_utils import get_file_url

from .organization.context import organization_identity_payload


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    organization_attribution = serializers.SerializerMethodField()
    dialogue_slug = serializers.CharField(source="dialogue.slug", read_only=True)
    content_encrypted = serializers.SerializerMethodField()
    aes_key_encrypted = serializers.SerializerMethodField()
    encrypted_for_device = serializers.SerializerMethodField()
    is_encrypted = serializers.SerializerMethodField()
    seen_by_users = serializers.SerializerMethodField()
    seen_count = serializers.SerializerMethodField()
    seen_by_organization = serializers.SerializerMethodField()
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
            'id', 'dialogue', 'dialogue_slug', 'sender', 'sender_type',
            'organization_attribution', 'timestamp', 'edited_at', 'is_edited',
            'seen_by_users', 'seen_count', 'seen_count_others',
            'seen_by_organization', 'is_delivered',
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

    def _organization_attribution(self, obj):
        try:
            return obj.organization_attribution
        except Exception:
            return None

    def _resolved_context(self, obj):
        return ConversationContextPolicy.resolve(obj.dialogue)

    def _operator_view(self) -> bool:
        return bool(self.context.get("organization_operator_view", False))

    def _external_organization_direct_view(self, obj) -> bool:
        context = self._resolved_context(obj)
        return (
            context.kind == ConversationContextKind.ORGANIZATION_DIRECT
            and not self._operator_view()
        )

    def get_sender(self, obj):
        if self._organization_attribution(obj) is not None:
            # Public presentation sender is the Organization; the human actor
            # is exposed only inside organization_attribution for operator UI.
            return None
        return SimpleCustomUserSerializer(
            obj.sender,
            context=self.context,
        ).data

    def get_sender_type(self, obj):
        return (
            "organization"
            if self._organization_attribution(obj) is not None
            else "user"
        )

    def get_organization_attribution(self, obj):
        attribution = self._organization_attribution(obj)
        if attribution is None:
            return None

        payload = {
            "sent_as_organization": True,
            "organization": organization_identity_payload(
                attribution.organization,
                request=self.context.get("request"),
            ),
            "actor": None,
            "actor_display_name": None,
            "actor_username": None,
            "actor_membership_public_id": None,
        }

        if self._operator_view():
            payload.update({
                "actor": SimpleCustomUserSerializer(
                    obj.sender,
                    context=self.context,
                ).data,
                "actor_display_name": attribution.actor_display_name_snapshot,
                "actor_username": attribution.actor_username_snapshot,
                "actor_membership_public_id": (
                    str(attribution.actor_membership_public_id_snapshot)
                    if attribution.actor_membership_public_id_snapshot
                    else None
                ),
            })

        return payload

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
    # Seen state --------------------------------------

    def get_seen_by_users(self, obj):
        if self._external_organization_direct_view(obj):
            # External participants never receive internal operator IDs.
            return []
        return list(obj.seen_by_users.values_list("id", flat=True))

    def get_seen_by_organization(self, obj):
        context = self._resolved_context(obj)
        if context.kind != ConversationContextKind.ORGANIZATION_DIRECT:
            return None

        participant_user_id = context.organization_context.participant_user_id
        if obj.sender_id != participant_user_id:
            return False

        return obj.seen_by_users.exclude(id=participant_user_id).exists()

    def get_seen_count(self, obj):
        """Number of viewers excluding the sender without leaking operators."""
        if self._external_organization_direct_view(obj):
            return 1 if self.get_seen_by_organization(obj) else 0
        return obj.seen_by_users.exclude(pk=obj.sender_id).count()

    def get_seen_count_others(self, obj):
        if self._external_organization_direct_view(obj):
            return 1 if self.get_seen_by_organization(obj) else 0

        request = self.context.get("request")
        qs = obj.seen_by_users.exclude(pk=obj.sender_id)
        if request and request.user and request.user.is_authenticated:
            qs = qs.exclude(pk=request.user.pk)
        return qs.count()

    # Pin state --------------------------------------

    def get_is_pinned(self, obj):
        if self._resolved_context(obj).kind == ConversationContextKind.ORGANIZATION_DIRECT:
            return False
        return obj.pins.exists()

    def get_pinned_position(self, obj):
        if self._resolved_context(obj).kind == ConversationContextKind.ORGANIZATION_DIRECT:
            return None
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
        if self._resolved_context(obj).kind == ConversationContextKind.ORGANIZATION_DIRECT:
            return {
                "message_id": obj.id,
                "total_count": 0,
                "counts": {
                    "like": 0,
                    "dislike": 0,
                    "gratitude": 0,
                    "heart": 0,
                    "encouragement": 0,
                },
                "items": [],
                "my_reaction": None,
            }
        request = self.context.get("request")
        acting_user = request.user if request and hasattr(request, "user") else None
        return build_message_reaction_summary(message=obj, acting_user=acting_user)


