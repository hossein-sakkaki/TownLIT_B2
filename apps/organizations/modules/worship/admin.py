# apps/organizations/modules/worship/admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin

from apps.organizations.modules.worship.models import (
    OrganizationMusicContribution, OrganizationMusicLicense, OrganizationMusicLicenseEvidence,
    OrganizationRightsParty, WorshipAuditLog, WorshipWorkspace,
)


@admin.register(WorshipWorkspace)
class WorshipWorkspaceAdmin(admin.ModelAdmin):
    list_display = ("id", "organization_name", "created_at")
    readonly_fields = ("public_id", "created_at", "updated_at")
    def organization_name(self, obj): return obj.activation.organization.name


@admin.register(OrganizationRightsParty)
class OrganizationRightsPartyAdmin(admin.ModelAdmin):
    list_display = ("rights_party", "workspace", "relationship", "is_active", "created_at")
    list_filter = ("relationship", "is_active")
    search_fields = ("rights_party__display_name", "rights_party__legal_name")


class OrganizationMusicLicenseEvidenceInline(admin.TabularInline):
    model = OrganizationMusicLicenseEvidence
    extra = 0
    readonly_fields = ("public_id", "sha256", "created_at")


@admin.register(OrganizationMusicLicense)
class OrganizationMusicLicenseAdmin(admin.ModelAdmin):
    list_display = ("title", "workspace", "status", "license_type", "effective_from", "effective_until")
    list_filter = ("status", "license_type", "territory_mode")
    search_fields = ("title", "reference", "license_version", "licensor__rights_party__display_name")
    readonly_fields = ("public_id", "activated_at", "revoked_at", "created_at", "updated_at")
    inlines = (OrganizationMusicLicenseEvidenceInline,)


@admin.register(OrganizationMusicContribution)
class OrganizationMusicContributionAdmin(admin.ModelAdmin):
    list_display = ("track", "workspace", "status", "primary_artist", "published_at", "revoked_at")
    list_filter = ("status",)
    search_fields = ("track__title", "primary_artist__display_name", "credit_text")
    readonly_fields = ("public_id", "license_snapshot", "published_at", "revoked_at", "created_at", "updated_at")


@admin.register(WorshipAuditLog)
class WorshipAuditLogAdmin(admin.ModelAdmin):
    list_display = ("workspace", "event", "entity_type", "actor", "created_at")
    list_filter = ("event",)
    search_fields = ("entity_type",)
    readonly_fields = tuple(field.name for field in WorshipAuditLog._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
