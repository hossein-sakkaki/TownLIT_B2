# apps/accounts/serializers/device_serializers.py

from django.db import transaction

from rest_framework import serializers

from apps.accounts.constants.devices import (
    MOBILE_DEVICE_PLATFORMS,
    SUPPORTED_DEVICE_PLATFORMS,
)
from apps.accounts.models.devices import UserDeviceKey
from apps.accounts.services.device_push_ownership import (
    claim_device_push_ownership,
    normalize_device_id,
    normalize_install_id,
    normalize_platform,
    normalize_push_token,
)


class UserDeviceKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDeviceKey

        fields = [
            "device_id",
            "device_name",
            "platform",
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
    device_id = serializers.CharField(
        max_length=100,
    )

    push_token = serializers.CharField(
        max_length=512,
        trim_whitespace=True,
    )

    platform = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )

    install_id = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
    )

    def validate_device_id(self, value: str) -> str:
        normalized = normalize_device_id(value)

        if not normalized:
            raise serializers.ValidationError(
                "Device ID is required."
            )

        return normalized

    def validate_push_token(self, value: str) -> str:
        normalized = normalize_push_token(value)

        if not normalized:
            raise serializers.ValidationError(
                "Push token is required."
            )

        return normalized

    def validate_platform(self, value: str) -> str:
        """
        Validate an explicitly supplied platform.

        An omitted platform never silently becomes Web here.
        """
        if not str(value or "").strip():
            return ""

        normalized = normalize_platform(value)

        if normalized not in SUPPORTED_DEVICE_PLATFORMS:
            raise serializers.ValidationError(
                "Platform must be web, ios, or android."
            )

        return normalized

    def validate_install_id(self, value: str) -> str:
        return normalize_install_id(value) or ""

    @transaction.atomic
    def save(
        self,
        *,
        user,
    ) -> UserDeviceKey:
        device_id = self.validated_data["device_id"]
        push_token = self.validated_data["push_token"]

        requested_platform = (
            self.validated_data.get("platform")
            or ""
        )

        requested_install_id = (
            self.validated_data.get("install_id")
            or ""
        )

        try:
            device = (
                UserDeviceKey.objects
                .select_for_update()
                .get(
                    user=user,
                    device_id=device_id,
                )
            )

        except UserDeviceKey.DoesNotExist as error:
            raise serializers.ValidationError(
                {
                    "device_id": (
                        "Register the device key before syncing "
                        "its push token."
                    )
                }
            ) from error

        existing_platform = normalize_platform(
            device.platform
        )

        if (
            existing_platform
            and requested_platform
            and existing_platform != requested_platform
        ):
            raise serializers.ValidationError(
                {
                    "platform": (
                        "Platform does not match the registered device."
                    )
                }
            )

        platform = (
            requested_platform
            or existing_platform
            or "web"
        )

        if platform not in SUPPORTED_DEVICE_PLATFORMS:
            raise serializers.ValidationError(
                {
                    "platform": (
                        "Platform must be web, ios, or android."
                    )
                }
            )

        # Mobile Push registration requires successful PoP verification.
        if (
            platform in MOBILE_DEVICE_PLATFORMS
            and not device.is_verified
        ):
            raise serializers.ValidationError(
                {
                    "device_id": (
                        "Complete device verification before "
                        "registering a mobile Push token."
                    )
                }
            )

        existing_install_id = normalize_install_id(
            device.install_id
        )

        if (
            existing_install_id
            and requested_install_id
            and existing_install_id != requested_install_id
        ):
            raise serializers.ValidationError(
                {
                    "install_id": (
                        "Install ID does not match the registered device."
                    )
                }
            )

        device.push_token = push_token
        device.platform = platform
        device.is_active = True

        update_fields = [
            "push_token",
            "platform",
            "is_active",
            "last_used",
        ]

        # Allow first-time install binding but never mutate an existing one here.
        if requested_install_id and not existing_install_id:
            device.install_id = requested_install_id
            update_fields.append("install_id")

        device.save(
            update_fields=update_fields
        )

        claim_result = claim_device_push_ownership(
            device_pk=device.pk,
        )

        return claim_result.device