# apps/subscriptions/admin/plans.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.contrib import admin

from apps.subscriptions.models import PlanEntitlement, SubscriptionPlan, SubscriptionPlanPrice


class SubscriptionPlanPriceInline(admin.TabularInline):
    model = SubscriptionPlanPrice
    extra = 0


class PlanEntitlementInline(admin.TabularInline):
    model = PlanEntitlement
    extra = 0


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "key",
        "name",
        "audience_key",
        "trial_key",
        "trial_duration_days",
        "is_public",
        "is_active",
        "sort_order",
    )
    list_filter = ("audience_key", "is_public", "is_active")
    search_fields = ("key", "name", "description")
    ordering = ("sort_order", "name")
    inlines = [SubscriptionPlanPriceInline, PlanEntitlementInline]
