# apps/subscriptions/serializers/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from rest_framework import serializers

from apps.subscriptions.models import Subscription, SubscriptionAccount
from apps.subscriptions.serializers.plans import SubscriptionPlanSerializer


class OrganizationSubscriptionAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionAccount
        fields = [
            "public_id",
            "status",
            "default_currency",
            "billing_email",
            "created_at",
            "updated_at",
            "closed_at",
        ]
        read_only_fields = fields


class OrganizationCurrentSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "public_id",
            "status",
            "plan",
            "billing_interval",
            "trial_started_at",
            "trial_ends_at",
            "current_period_started_at",
            "current_period_ends_at",
            "cancel_at_period_end",
            "cancel_requested_at",
            "canceled_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrganizationSubscriptionEligibilitySerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    code = serializers.CharField()
    detail = serializers.CharField()
    is_verified = serializers.BooleanField()


class OrganizationSubscriptionOverviewSerializer(serializers.Serializer):
    audience_key = serializers.CharField()
    account = OrganizationSubscriptionAccountSerializer()
    eligibility = OrganizationSubscriptionEligibilitySerializer()
    current_subscription = OrganizationCurrentSubscriptionSerializer(
        allow_null=True,
    )
    available_plans = SubscriptionPlanSerializer(many=True)
    effective_entitlements = serializers.DictField(
        child=serializers.JSONField(),
    )


class OrganizationSubscriptionAccountUpdateSerializer(serializers.Serializer):
    billing_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
