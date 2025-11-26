# apps/notifications/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import UserNotificationPreference, Notification
from apps.accounts.serializers import UserMiniSerializer
from .constants import NOTIFICATION_PREF_METADATA, CHANNEL_EMAIL, CHANNEL_PUSH


# -------------------------------------------------------------------
# User Notification Preference Serializer
# -------------------------------------------------------------------
class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True
    )

    # NEW FIELDS
    category = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    email_enabled = serializers.SerializerMethodField()
    push_enabled = serializers.SerializerMethodField()

    class Meta:
        model = UserNotificationPreference
        fields = [
            'id',
            'notification_type',
            'notification_type_display',
            'enabled',

            # NEW
            'category',
            'label',
            'description',
            'email_enabled',
            'push_enabled',
        ]
        read_only_fields = ['id', 'notification_type_display']

    # -------------------------- Metadata -------------------------

    def get_category(self, obj):
        return NOTIFICATION_PREF_METADATA.get(obj.notification_type, {}).get("category")

    def get_label(self, obj):
        return NOTIFICATION_PREF_METADATA.get(obj.notification_type, {}).get("label")

    def get_description(self, obj):
        return NOTIFICATION_PREF_METADATA.get(obj.notification_type, {}).get("description")

    # -------------------------- Channels --------------------------

    def get_email_enabled(self, obj):
        return bool(obj.channels_mask & CHANNEL_EMAIL)

    def get_push_enabled(self, obj):
        return bool(obj.channels_mask & CHANNEL_PUSH)

    # -------------------------- Update override -------------------

    def update(self, instance, validated_data):
        """
        We support:
        - enabled (main toggle)
        - email_enabled (boolean)
        - push_enabled (boolean)
        via PATCH
        """

        request = self.context.get("request")
        if request and request.data:
            # Manage channel toggles
            push_val = request.data.get("push_enabled")
            email_val = request.data.get("email_enabled")

            # ---- PUSH ----
            if push_val is not None:
                if bool(push_val):
                    instance.channels_mask |= CHANNEL_PUSH
                else:
                    instance.channels_mask &= ~CHANNEL_PUSH

            # ---- EMAIL ----
            if email_val is not None:
                if bool(email_val):
                    instance.channels_mask |= CHANNEL_EMAIL
                else:
                    instance.channels_mask &= ~CHANNEL_EMAIL

        # regular "enabled" field
        instance.enabled = validated_data.get("enabled", instance.enabled)

        instance.save()
        return instance

    def validate(self, attrs):
        if 'user' in self.context and self.instance is None:
            attrs['user'] = self.context['user']
        return attrs

# -------------------------------------------------------------------
# Notification Serializer
# -------------------------------------------------------------------
class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True
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

            # Relations
            "target_content_type",
            "target_object_id",
            "action_content_type",
            "action_object_id",

            # Actor info (nested)
            "actor",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "target_content_type",
            "target_object_id",
            "action_content_type",
            "action_object_id",
            "notification_type_display"
        ]

# -------------------------------------------------------------------
# Mark Read Serializer
# -------------------------------------------------------------------
class NotificationMarkReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['is_read']

    def update(self, instance, validated_data):
        # mark read + timestamp
        instance.is_read = True
        instance.read_at = timezone.now()
        instance.save(update_fields=['is_read', 'read_at'])
        return instance
