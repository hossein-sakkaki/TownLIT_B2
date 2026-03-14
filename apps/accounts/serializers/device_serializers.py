# apps/accounts/serializers/device_serializers.py

from rest_framework import serializers
from django.utils import timezone

from ..models import UserDeviceKey


class UserDeviceKeySerializer(serializers.ModelSerializer):

    class Meta:
        model = UserDeviceKey

        fields = [
            "device_id",
            "device_name",
            "user_agent",
            "ip_address",
            "created_at",
            "last_used",
            "is_active",
            "location_city",
            "location_region",
            "location_country",
            "is_verified",
            "verified_at",
        ]


class DevicePushTokenSerializer(serializers.Serializer):

    device_id = serializers.CharField(max_length=100)
    push_token = serializers.CharField(max_length=512)
    platform = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def save(self, user):

        device_id = self.validated_data["device_id"]
        push_token = self.validated_data["push_token"]
        platform = self.validated_data.get("platform") or "web"

        obj, created = UserDeviceKey.objects.get_or_create(
            user=user,
            device_id=device_id,
            defaults={
                "platform": platform,
                "push_token": push_token,
            },
        )

        if not created:
            obj.platform = platform
            obj.push_token = push_token
            obj.is_active = True
            obj.last_used = timezone.now()

            obj.save(update_fields=["platform", "push_token", "is_active", "last_used"])

        return obj