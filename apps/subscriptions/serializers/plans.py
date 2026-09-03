# apps/subscriptions/serializers/plans.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.utils import timezone
from rest_framework import serializers

from apps.subscriptions.models import SubscriptionPlan, SubscriptionPlanPrice


class SubscriptionPlanPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlanPrice
        fields = [
            "id",
            "currency",
            "billing_interval",
            "amount",
            "valid_from",
            "valid_until",
        ]
        read_only_fields = fields


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    prices = serializers.SerializerMethodField()
    entitlements = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "key",
            "name",
            "audience_key",
            "description",
            "trial_key",
            "trial_duration_days",
            "prices",
            "entitlements",
        ]
        read_only_fields = fields

    def get_prices(self, obj):
        now = timezone.now()
        prices = [
            price
            for price in obj.prices.all()
            if price.is_active
            and price.valid_from <= now
            and (price.valid_until is None or price.valid_until > now)
        ]
        return SubscriptionPlanPriceSerializer(prices, many=True).data

    def get_entitlements(self, obj):
        return {
            item.entitlement.key: item.value
            for item in obj.plan_entitlements.all()
            if item.entitlement.is_active
        }
