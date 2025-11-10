from rest_framework import serializers
from django.utils import timezone
from .models import UserNotificationPreference, Notification

# User Notification Preference Serializer -----------------------------------------------------
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

# Notification Serializer --------------------------------------------------------------------
class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'message', 'notification_type', 'notification_type_display',
            'created_at', 'is_read', 'content_type', 'object_id', 'content_object', 'link'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'content_type', 'object_id', 'content_object', 'notification_type_display']


class NotificationMarkReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['is_read']

    def update(self, instance, validated_data):
        # Mark read + timestamp
        instance.is_read = True
        instance.read_at = timezone.now()
        instance.save(update_fields=['is_read', 'read_at'])
        return instance