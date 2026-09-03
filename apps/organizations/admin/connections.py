# apps/organizations/admin/connections.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import OrganizationConnection


@admin.register(OrganizationConnection)
class OrganizationConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "user",
        "relationship_type",
        "status",
        "started_at",
        "ended_at",
    )
    list_filter = (
        "relationship_type",
        "status",
    )
    search_fields = (
        "organization__name",
        "user__username",
        "user__email",
    )
    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )
