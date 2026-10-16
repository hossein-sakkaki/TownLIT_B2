# apps/organizations/admin/audit.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

import json

from django.contrib import admin
from django.utils.text import Truncator

from apps.organizations.models import OrganizationAuditLog


@admin.register(OrganizationAuditLog)
class OrganizationAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "organization",
        "action",
        "source",
        "actor",
        "target_user",
        "metadata_summary",
    )
    list_filter = (
        "action",
        "source",
        "created_at",
    )
    search_fields = (
        "organization__name",
        "organization__slug",
        "actor__username",
        "actor__email",
        "target_user__username",
        "target_user__email",
        "verification_case__public_id",
        "membership_request__public_id",
        "membership__public_id",
        "relationship__public_id",
        "governance_proposal__public_id",
    )
    list_select_related = (
        "organization",
        "actor",
        "target_user",
        "membership",
        "membership_request",
        "role_assignment",
        "verification_case",
        "relationship",
        "governance_proposal",
        "module_activation",
    )
    ordering = ("-created_at", "-id")
    list_per_page = 100
    show_full_result_count = False
    date_hierarchy = "created_at"

    readonly_fields = tuple(
        field.name
        for field in OrganizationAuditLog._meta.fields
    )

    fieldsets = (
        (
            "Event",
            {
                "fields": (
                    "organization",
                    "action",
                    "source",
                    "created_at",
                ),
            },
        ),
        (
            "Actors",
            {
                "fields": (
                    "actor",
                    "target_user",
                ),
            },
        ),
        (
            "Related organization records",
            {
                "fields": (
                    "membership",
                    "membership_request",
                    "role_assignment",
                    "verification_case",
                    "relationship",
                    "governance_proposal",
                    "module_activation",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("metadata",),
            },
        ),
    )

    @admin.display(description="Metadata")
    def metadata_summary(self, obj):
        if not obj.metadata:
            return "—"

        serialized = json.dumps(
            obj.metadata,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
        return Truncator(serialized).chars(140)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
