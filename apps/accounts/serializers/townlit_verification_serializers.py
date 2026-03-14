# apps/accounts/serializers/townlit_verification_serializers.py

from rest_framework import serializers


class TownlitVerificationEligibilitySerializer(serializers.Serializer):
    is_member = serializers.BooleanField()
    identity_verified = serializers.BooleanField()

    score = serializers.IntegerField()
    threshold = serializers.IntegerField()
    remaining_score = serializers.IntegerField()

    hard_requirements_ready = serializers.BooleanField()
    score_ready = serializers.BooleanField()

    eligible_for_initial_gold_unlock = serializers.BooleanField()
    already_townlit_verified = serializers.BooleanField()

    missing_requirements = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )

    is_townlit_verified = serializers.BooleanField(required=False)
    townlit_verified_at = serializers.DateTimeField(required=False, allow_null=True)
    townlit_verified_reason = serializers.CharField(required=False, allow_null=True)


class TownlitVerificationStatusSerializer(serializers.Serializer):
    is_member = serializers.BooleanField()
    identity_verified = serializers.BooleanField()
    is_townlit_verified = serializers.BooleanField()
    townlit_verified_at = serializers.DateTimeField(allow_null=True)
    townlit_verified_reason = serializers.CharField(allow_null=True)

    score = serializers.IntegerField()
    threshold = serializers.IntegerField()
    remaining_score = serializers.IntegerField()

    hard_requirements_ready = serializers.BooleanField()
    score_ready = serializers.BooleanField()
    missing_requirements = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )