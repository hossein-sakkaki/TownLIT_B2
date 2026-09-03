# apps/subscriptions/admin/subscriptions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.contrib import admin

from apps.subscriptions.models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "public_id",
        "account",
        "plan",
        "status",
        "billing_interval",
        "trial_ends_at",
        "current_period_ends_at",
        "cancel_at_period_end",
        "cancel_requested_at",
    )
    list_filter = ("status", "billing_interval", "plan")
    search_fields = (
        "public_id",
        "account__public_id",
        "provider_subscription_reference",
    )
    readonly_fields = ("public_id", "created_at", "updated_at")
    list_select_related = ("account", "plan")
