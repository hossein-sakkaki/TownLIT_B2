# apps/subscriptions/admin/entitlements.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.contrib import admin

from apps.subscriptions.models import EntitlementDefinition, EntitlementGrant


@admin.register(EntitlementDefinition)
class EntitlementDefinitionAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "name", "value_type", "default_value", "is_active")
    list_filter = ("value_type", "is_active")
    search_fields = ("key", "name", "description")


@admin.register(EntitlementGrant)
class EntitlementGrantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "account",
        "entitlement",
        "value",
        "source",
        "priority",
        "is_active",
        "starts_at",
        "ends_at",
    )
    list_filter = ("source", "is_active", "entitlement")
    search_fields = ("account__public_id", "entitlement__key", "reason")
    list_select_related = ("account", "entitlement", "source_subscription", "granted_by")
