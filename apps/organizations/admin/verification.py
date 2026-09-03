# apps/organizations/admin/verification.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
    OrganizationVerificationGrant,
)


@admin.register(OrganizationVerificationCase)
class OrganizationVerificationCaseAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "path",
        "status",
        "submitted_at",
        "decision_at",
        "created_at",
    )
    list_filter = ("path", "status", "jurisdiction_country")
    search_fields = (
        "organization__name",
        "organization__slug",
        "public_id",
        "legal_name",
        "registration_number",
    )
    readonly_fields = (
        "public_id",
        "current_slot",
        "renewal_of",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "review_started_at",
        "decision_at",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationVerificationDocument)
class OrganizationVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "verification_case",
        "document_type",
        "review_status",
        "is_active",
        "created_at",
    )
    list_filter = ("document_type", "review_status", "is_active")
    search_fields = (
        "verification_case__organization__name",
        "public_id",
        "document_number",
        "title",
    )
    readonly_fields = (
        "public_id",
        "uploaded_by",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationVerificationGrant)
class OrganizationVerificationGrantAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "grant_type",
        "status",
        "granted_at",
        "expires_at",
        "revoked_at",
    )
    list_filter = ("grant_type", "status")
    search_fields = (
        "organization__name",
        "organization__slug",
        "public_id",
    )
    readonly_fields = (
        "public_id",
        "active_slot",
        "organization",
        "verification_case",
        "grant_type",
        "relationship",
        "supersedes",
        "granted_by",
        "granted_at",
        "created_at",
        "updated_at",
    )
