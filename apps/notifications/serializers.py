# apps/notifications/serializers.py

from rest_framework import serializers
from django.utils import timezone

from .models import UserNotificationPreference, Notification
from apps.accounts.serializers.user_serializers import UserMiniSerializer
from .constants import (
    NOTIFICATION_PREF_METADATA,
    CHANNEL_EMAIL,
    CHANNEL_PUSH,
    notification_supports_email,
    notification_supports_push,
    sanitize_notification_channels,
)


# -------------------------------------------------------------------
# User Notification Preference Serializer
# -------------------------------------------------------------------
class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source="get_notification_type_display",
        read_only=True,
    )

    category = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    email_enabled = serializers.SerializerMethodField()
    push_enabled = serializers.SerializerMethodField()

    # New capability fields for frontend.
    # The frontend should hide the email toggle when email_supported is false.
    email_supported = serializers.SerializerMethodField()
    push_supported = serializers.SerializerMethodField()
    supported_channels = serializers.SerializerMethodField()

    class Meta:
        model = UserNotificationPreference
        fields = [
            "id",
            "notification_type",
            "notification_type_display",
            "enabled",

            "category",
            "label",
            "description",

            "email_enabled",
            "push_enabled",

            "email_supported",
            "push_supported",
            "supported_channels",
        ]
        read_only_fields = [
            "id",
            "notification_type_display",
            "email_supported",
            "push_supported",
            "supported_channels",
        ]

    # -------------------------- Metadata -------------------------

    def get_category(self, obj):
        return NOTIFICATION_PREF_METADATA.get(obj.notification_type, {}).get("category")

    def get_label(self, obj):
        return NOTIFICATION_PREF_METADATA.get(obj.notification_type, {}).get("label")

    def get_description(self, obj):
        return NOTIFICATION_PREF_METADATA.get(obj.notification_type, {}).get("description")

    # -------------------------- Channel support --------------------------

    def get_email_supported(self, obj):
        return notification_supports_email(obj.notification_type)

    def get_push_supported(self, obj):
        return notification_supports_push(obj.notification_type)

    def get_supported_channels(self, obj):
        channels = []

        if notification_supports_push(obj.notification_type):
            channels.append("push")

        if notification_supports_email(obj.notification_type):
            channels.append("email")

        return channels

    # -------------------------- Channel values --------------------------

    def get_email_enabled(self, obj):
        if not notification_supports_email(obj.notification_type):
            return False

        return bool(obj.channels_mask & CHANNEL_EMAIL)

    def get_push_enabled(self, obj):
        if not notification_supports_push(obj.notification_type):
            return False

        return bool(obj.channels_mask & CHANNEL_PUSH)

    # -------------------------- Update override -------------------

    def update(self, instance, validated_data):
        """
        Supports:
        - enabled
        - email_enabled
        - push_enabled

        Unsupported channels are ignored and stripped.
        Example:
        - comment/reaction/friendship/feed types cannot enable email anymore.
        """
        request = self.context.get("request")

        if request and request.data:
            push_val = request.data.get("push_enabled")
            email_val = request.data.get("email_enabled")

            if push_val is not None and notification_supports_push(instance.notification_type):
                if bool(push_val):
                    instance.channels_mask |= CHANNEL_PUSH
                else:
                    instance.channels_mask &= ~CHANNEL_PUSH

            if email_val is not None:
                if notification_supports_email(instance.notification_type):
                    if bool(email_val):
                        instance.channels_mask |= CHANNEL_EMAIL
                    else:
                        instance.channels_mask &= ~CHANNEL_EMAIL
                else:
                    instance.channels_mask &= ~CHANNEL_EMAIL

        instance.enabled = validated_data.get("enabled", instance.enabled)

        instance.channels_mask = sanitize_notification_channels(
            instance.notification_type,
            instance.channels_mask,
        )

        instance.save()
        return instance

    def validate(self, attrs):
        if "user" in self.context and self.instance is None:
            attrs["user"] = self.context["user"]

        return attrs


# -------------------------------------------------------------------
# Notification Serializer
# -------------------------------------------------------------------
class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source="get_notification_type_display",
        read_only=True,
    )

    actor = UserMiniSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "message",
            "notification_type",
            "notification_type_display",
            "created_at",
            "is_read",
            "read_at",
            "link",

            "target_content_type",
            "target_object_id",
            "action_content_type",
            "action_object_id",

            "actor",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "target_content_type",
            "target_object_id",
            "action_content_type",
            "action_object_id",
            "notification_type_display",
        ]


# -------------------------------------------------------------------
# Mark Read Serializer
# -------------------------------------------------------------------
class NotificationMarkReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["is_read"]

    def update(self, instance, validated_data):
        instance.is_read = True
        instance.read_at = timezone.now()
        instance.save(update_fields=["is_read", "read_at"])
        return instance