# apps/conversation/serializers/dialogue.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.db.models import Count
from rest_framework import serializers

from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.conversation.mixins import GroupAvatarURLMixin
from apps.conversation.models import Dialogue, DialoguePin
from apps.conversation.policies import (
    ConversationAccessPolicy,
    ConversationContextKind,
    ConversationContextPolicy,
)
from apps.conversation.services.boundary_access import check_private_dialogue_boundary
from apps.conversation.utils import get_websocket_url
from apps.core.boundaries.serializers import boundary_unavailable_reason_to_text

from .message import MessageSerializer
from .organization.context import organization_conversation_context_payload
from .participant import DialogueParticipantSerializer


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
    conversation_context = serializers.SerializerMethodField()
    organization_context = serializers.SerializerMethodField()

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
            "conversation_context",
            "organization_context",
        ]
    # -------------------------------------------------------------------
    # Conversation context
    # -------------------------------------------------------------------

    def get_conversation_context(self, obj):
        return ConversationContextPolicy.resolve(obj).kind.value

    def get_organization_context(self, obj):
        request = self.context.get("request")
        return organization_conversation_context_payload(
            obj,
            request=request,
        )

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

        resolved = ConversationContextPolicy.resolve(obj)
        if resolved.kind == ConversationContextKind.ORGANIZATION_DIRECT:
            return ConversationAccessPolicy.can_send_as_self(
                dialogue=obj,
                user=request.user,
            )

        # Group membership/history stays available.
        # Boundary only blocks Personal Direct interaction.
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
        access = ConversationAccessPolicy.can_view(
            dialogue=obj,
            user=request.user,
        )
        if not access.allowed:
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

    def get_group_avatar_url(self, obj):
        organization_context = organization_conversation_context_payload(
            obj,
            request=self.context.get("request"),
        )
        if organization_context:
            avatar_url = (
                organization_context
                .get("organization", {})
                .get("avatar_url")
            )
            if avatar_url:
                return avatar_url

        return GroupAvatarURLMixin.get_group_avatar_url(self, obj)

    def get_group_avatar_cdn_url(self, obj):
        organization_context = organization_conversation_context_payload(
            obj,
            request=self.context.get("request"),
        )
        if organization_context:
            avatar_url = (
                organization_context
                .get("organization", {})
                .get("avatar_cdn_url")
            )
            if avatar_url:
                return avatar_url

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
