# apps/organization_media/admin.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

from django.contrib import admin
from .models import OrganizationMediaAsset


@admin.register(OrganizationMediaAsset)
class OrganizationMediaAssetAdmin(admin.ModelAdmin):
    list_display = ("public_id", "organization", "kind", "status", "created_at")
    search_fields = ("public_id", "organization__name")
    list_filter = ("kind", "status")
    readonly_fields = ("public_id", "created_at", "updated_at")
