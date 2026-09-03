# apps/organizations/admin/memberships.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

from django.contrib import admin

from apps.organizations.models import (
    OrganizationMembership,
    OrganizationMembershipRequest,
)


@admin.register(OrganizationMembershipRequest)
class OrganizationMembershipRequestAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "member",
        "direction",
        "status",
        "created_at",
        "expires_at",
    )
    list_filter = (
        "direction",
        "status",
    )
    search_fields = (
        "organization__name",
        "member__user__username",
        "member__user__email",
    )
    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "member",
        "status",
        "joined_at",
        "ended_at",
    )
    list_filter = ("status",)
    search_fields = (
        "organization__name",
        "member__user__username",
        "member__user__email",
    )
    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )
