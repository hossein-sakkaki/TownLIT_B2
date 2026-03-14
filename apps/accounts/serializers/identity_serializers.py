# apps/accounts/serializers/identity_serializers.py

from rest_framework import serializers

from ..models import IdentityVerification


class IdentityStartSerializer(serializers.Serializer):
    success_url = serializers.URLField(required=False)
    failure_url = serializers.URLField(required=False)


class IdentityStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = IdentityVerification

        fields = (
            "method",
            "status",
            "level",
            "verified_at",
            "revoked_at",
            "rejected_at",
            "risk_flag",
        )


class IdentityRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False)