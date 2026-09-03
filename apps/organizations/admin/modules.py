# apps/organizations/admin/modules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationModuleActivation,
    OrganizationModuleDefinition,
)


@admin.register(OrganizationModuleDefinition)
class OrganizationModuleDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "name",
        "requires_verification",
        "requires_entitlement",
        "fallback_access_mode",
        "sort_order",
        "is_active",
    )
    list_filter = (
        "requires_verification",
        "requires_entitlement",
        "fallback_access_mode",
        "is_active",
    )
    search_fields = (
        "key",
        "name",
        "entitlement_key",
    )
    ordering = ("sort_order", "name")
    readonly_fields = (
        "key",
        "entitlement_key",
        "schema_version",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrganizationModuleActivation)
class OrganizationModuleActivationAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "module",
        "status",
        "visibility",
        "activated_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "visibility",
        "module",
    )
    search_fields = (
        "organization__name",
        "organization__slug",
        "module__key",
        "module__name",
        "display_name",
    )
    autocomplete_fields = (
        "organization",
        "module",
        "activated_by",
        "last_changed_by",
    )
    readonly_fields = (
        "public_id",
        "organization",
        "module",
        "display_name",
        "summary",
        "visibility",
        "status",
        "activated_by",
        "last_changed_by",
        "activated_at",
        "disabled_at",
        "suspended_at",
        "configuration",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
