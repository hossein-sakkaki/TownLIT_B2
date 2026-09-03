# apps/organizations/admin/hierarchy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationRelationship,
    OrganizationRelationshipConsent,
)


@admin.register(OrganizationRelationship)
class OrganizationRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        "source_organization",
        "relationship_type",
        "target_organization",
        "status",
        "activated_at",
        "created_at",
    )
    list_filter = ("relationship_type", "status")
    search_fields = (
        "public_id",
        "source_organization__name",
        "target_organization__name",
    )
    readonly_fields = (
        "public_id",
        "current_slot",
        "authority_slot",
        "requested_by_organization",
        "requested_by",
        "activated_at",
        "suspended_at",
        "ended_at",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationRelationshipConsent)
class OrganizationRelationshipConsentAdmin(admin.ModelAdmin):
    list_display = (
        "relationship",
        "organization",
        "status",
        "decided_at",
    )
    list_filter = ("status",)
    search_fields = (
        "relationship__public_id",
        "organization__name",
    )
    readonly_fields = (
        "relationship",
        "organization",
        "governance_proposal",
        "decided_by",
        "decided_at",
        "created_at",
        "updated_at",
    )
