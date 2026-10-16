# apps/organizations/admin/memberships.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from apps.organizations.constants import (
    MembershipRequestStatus,
    OrganizationMembershipStatus,
)
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
        "status_badge",
        "created_at",
        "expires_at",
        "responded_at",
    )
    list_filter = (
        "direction",
        "status",
        "created_at",
        "expires_at",
    )
    search_fields = (
        "public_id",
        "organization__name",
        "organization__slug",
        "member__user__username",
        "member__user__email",
        "initiated_by__email",
        "responded_by__email",
    )
    list_select_related = (
        "organization",
        "member__user",
        "initiated_by",
        "responded_by",
    )
    ordering = ("-created_at", "-id")
    list_per_page = 75
    show_full_result_count = False
    date_hierarchy = "created_at"

    readonly_fields = tuple(
        field.name
        for field in OrganizationMembershipRequest._meta.fields
    )

    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "public_id",
                    "organization",
                    "member",
                    "direction",
                    "status",
                    "message",
                    "response_message",
                ),
            },
        ),
        (
            "Actors & timing",
            {
                "fields": (
                    "initiated_by",
                    "responded_by",
                    "created_at",
                    "expires_at",
                    "responded_at",
                    "updated_at",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "pending_slot",
                    "metadata",
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            MembershipRequestStatus.PENDING: "#0d6efd",
            MembershipRequestStatus.ACCEPTED: "#198754",
            MembershipRequestStatus.REJECTED: "#dc3545",
            MembershipRequestStatus.WITHDRAWN: "#6c757d",
            MembershipRequestStatus.CANCELED: "#6c757d",
            MembershipRequestStatus.EXPIRED: "#fd7e14",
        }

        label = obj.get_status_display()

        if (
            obj.status == MembershipRequestStatus.PENDING
            and obj.expires_at
            and obj.expires_at <= timezone.now()
        ):
            label = "Pending (expired)"

        return format_html(
            '<span style="display:inline-block;padding:2px 8px;'
            'border-radius:999px;background:{};color:#fff;font-weight:600;">'
            "{}</span>",
            colors.get(obj.status, "#6c757d"),
            label,
        )


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "member",
        "status_badge",
        "approved_by",
        "joined_at",
        "suspended_at",
        "ended_at",
    )
    list_filter = (
        "status",
        "joined_at",
        "suspended_at",
        "ended_at",
    )
    search_fields = (
        "public_id",
        "organization__name",
        "organization__slug",
        "member__user__username",
        "member__user__email",
        "approved_by__email",
        "source_request__public_id",
    )
    list_select_related = (
        "organization",
        "member__user",
        "connection",
        "source_request",
        "approved_by",
    )
    ordering = ("-joined_at", "-id")
    list_per_page = 75
    show_full_result_count = False
    date_hierarchy = "joined_at"

    readonly_fields = tuple(
        field.name
        for field in OrganizationMembership._meta.fields
    )

    fieldsets = (
        (
            "Membership",
            {
                "fields": (
                    "public_id",
                    "organization",
                    "member",
                    "status",
                    "joined_at",
                    "suspended_at",
                    "ended_at",
                    "end_reason",
                ),
            },
        ),
        (
            "Source & access",
            {
                "fields": (
                    "connection",
                    "source_request",
                    "approved_by",
                ),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "current_slot",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            OrganizationMembershipStatus.ACTIVE: "#198754",
            OrganizationMembershipStatus.SUSPENDED: "#fd7e14",
            OrganizationMembershipStatus.ENDED: "#6c757d",
        }
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;'
            'border-radius:999px;background:{};color:#fff;font-weight:600;">'
            "{}</span>",
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )
