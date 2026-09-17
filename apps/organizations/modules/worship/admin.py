# apps/organizations/modules/worship/admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from django.contrib import admin

from apps.organizations.modules.worship.models import (
    OrganizationMusicContribution,
    OrganizationMusicLicense,
    OrganizationMusicLicenseEvidence,
    OrganizationRightsParty,
    WorshipAuditLog,
    WorshipWorkspace,
)


class WorshipServiceManagedAdminMixin:
    """
    Keep service-managed lifecycle records read-only in Django Admin.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorshipLegalAdminMixin(WorshipServiceManagedAdminMixin):
    """
    Restrict private legal records to platform superusers.
    """

    def has_view_permission(self, request, obj=None):
        user = getattr(request, "user", None)

        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_superuser", False)
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if not self.has_view_permission(request):
            return queryset.none()

        return queryset


@admin.register(WorshipWorkspace)
class WorshipWorkspaceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization_name",
        "created_at",
    )

    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "activation__organization__name",
        "activation__organization__slug",
    )

    def organization_name(self, obj):
        return obj.activation.organization.name


@admin.register(OrganizationRightsParty)
class OrganizationRightsPartyAdmin(
    WorshipLegalAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "rights_party",
        "workspace",
        "relationship",
        "is_active",
        "created_at",
    )

    list_filter = (
        "relationship",
        "is_active",
    )

    search_fields = (
        "rights_party__display_name",
        "rights_party__legal_name",
    )

    readonly_fields = (
        "id",
        "public_id",
        "workspace",
        "rights_party",
        "relationship",
        "is_active",
        "metadata",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationMusicLicense)
class OrganizationMusicLicenseAdmin(
    WorshipLegalAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "title",
        "workspace",
        "status",
        "license_type",
        "effective_from",
        "effective_until",
    )

    list_filter = (
        "status",
        "license_type",
        "territory_mode",
    )

    search_fields = (
        "title",
        "reference",
        "license_version",
        "licensor__rights_party__display_name",
    )

    readonly_fields = tuple(
        field.name
        for field in OrganizationMusicLicense._meta.fields
    )


@admin.register(OrganizationMusicLicenseEvidence)
class OrganizationMusicLicenseEvidenceAdmin(
    WorshipLegalAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "title",
        "license",
        "evidence_type",
        "sha256",
        "captured_at",
        "created_at",
    )

    list_filter = (
        "evidence_type",
    )

    search_fields = (
        "title",
        "sha256",
        "license__title",
        "license__reference",
    )

    readonly_fields = tuple(
        field.name
        for field in OrganizationMusicLicenseEvidence._meta.fields
    )


@admin.register(OrganizationMusicContribution)
class OrganizationMusicContributionAdmin(
    WorshipServiceManagedAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "track",
        "workspace",
        "status",
        "primary_artist",
        "published_at",
        "revoked_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "track__title",
        "primary_artist__display_name",
        "credit_text",
    )

    readonly_fields = tuple(
        field.name
        for field in OrganizationMusicContribution._meta.fields
    )


@admin.register(WorshipAuditLog)
class WorshipAuditLogAdmin(
    WorshipServiceManagedAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "workspace",
        "event",
        "entity_type",
        "actor",
        "created_at",
    )

    list_filter = (
        "event",
    )

    search_fields = (
        "entity_type",
    )

    readonly_fields = tuple(
        field.name
        for field in WorshipAuditLog._meta.fields
    )