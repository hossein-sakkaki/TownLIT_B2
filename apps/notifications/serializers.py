# apps/notifications/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import UserNotificationPreference, Notification
from apps.accounts.serializers import UserMiniSerializer

# -------------------------------------------------------------------
# User Notification Preference Serializer
# -------------------------------------------------------------------
class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = UserNotificationPreference
        fields = ['id', 'notification_type', 'notification_type_display', 'enabled']
        read_only_fields = ['id', 'notification_type_display']

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
