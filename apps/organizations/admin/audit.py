# apps/organizations/admin/audit.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import OrganizationAuditLog


@admin.register(OrganizationAuditLog)
class OrganizationAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "action",
        "source",
        "actor",
        "target_user",
        "created_at",
    )
    list_filter = (
        "action",
        "source",
    )
    search_fields = (
        "organization__name",
        "actor__username",
        "target_user__username",
    )
    readonly_fields = [
        field.name
        for field in OrganizationAuditLog._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
