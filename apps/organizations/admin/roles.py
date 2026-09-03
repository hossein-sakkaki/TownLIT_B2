# apps/organizations/admin/roles.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationPermission,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRolePermission,
)


class OrganizationRolePermissionInline(admin.TabularInline):
    model = OrganizationRolePermission
    extra = 0


@admin.register(OrganizationPermission)
class OrganizationPermissionAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "name",
        "category",
        "is_active",
    )
    list_filter = (
        "category",
        "is_active",
    )
    search_fields = (
        "key",
        "name",
    )


@admin.register(OrganizationRole)
class OrganizationRoleAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "key",
        "name",
        "priority",
        "is_system",
        "is_protected",
        "is_active",
    )
    list_filter = (
        "is_system",
        "is_protected",
        "is_active",
    )
    search_fields = (
        "organization__name",
        "key",
        "name",
    )
    inlines = [OrganizationRolePermissionInline]


@admin.register(OrganizationRoleAssignment)
class OrganizationRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "membership",
        "role",
        "scope_type",
        "scope_key",
        "is_active",
        "starts_at",
        "ends_at",
    )
    list_filter = (
        "scope_type",
        "is_active",
    )
    search_fields = (
        "membership__organization__name",
        "membership__member__user__username",
        "role__key",
    )
    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )
