# apps/organization_content/admin.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

from django.contrib import admin
from .models import OrganizationFeedEntry, OrganizationUpdate, OrganizationUpdateMedia


@admin.register(OrganizationUpdate)
class OrganizationUpdateAdmin(admin.ModelAdmin):
    list_display = ("public_id", "organization", "status", "published_at")
    search_fields = ("public_id", "organization__name")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(OrganizationFeedEntry)
class OrganizationFeedEntryAdmin(admin.ModelAdmin):
    list_display = ("public_id", "organization", "source", "is_active", "expires_at")
    search_fields = ("public_id", "organization__name")
    list_filter = ("source", "is_active", "is_pinned")
    readonly_fields = ("public_id", "created_at", "updated_at")

admin.site.register(OrganizationUpdateMedia)
