# apps/subscriptions/admin/trials.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.contrib import admin

from apps.subscriptions.models import SubscriptionTrialUsage


@admin.register(SubscriptionTrialUsage)
class SubscriptionTrialUsageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "account",
        "trial_key",
        "subscription",
        "started_at",
        "ends_at",
    )
    search_fields = ("account__public_id", "trial_key", "subscription__public_id")
    list_select_related = ("account", "subscription")
    readonly_fields = (
        "account",
        "trial_key",
        "subscription",
        "started_at",
        "ends_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
