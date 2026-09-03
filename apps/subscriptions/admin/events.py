# apps/subscriptions/admin/events.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.contrib import admin

from apps.subscriptions.models import SubscriptionEvent


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "source",
        "account",
        "subscription",
        "actor",
        "occurred_at",
    )
    list_filter = ("source", "event_type")
    search_fields = ("event_type", "dedupe_key", "account__public_id")
    readonly_fields = (
        "account",
        "subscription",
        "event_type",
        "source",
        "actor",
        "dedupe_key",
        "payload",
        "occurred_at",
        "created_at",
    )
    list_select_related = ("account", "subscription", "actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
