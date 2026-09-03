# apps/organizations/admin/organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "status",
        "visibility",
        "country",
        "created_at",
    )
    list_filter = (
        "kind",
        "status",
        "visibility",
        "country",
    )
    search_fields = (
        "name",
        "slug",
        "public_id",
        "public_email",
    )
    readonly_fields = (
        "public_id",
        "slug",
        "created_by",
        "subscription_account",
        "created_at",
        "updated_at",
    )
    ordering = ("name",)
