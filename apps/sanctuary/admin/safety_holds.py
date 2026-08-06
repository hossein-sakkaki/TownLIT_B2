# apps/sanctuary/admin/safety_holds.py

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.sanctuary.models import (
    SanctuarySafetyHold,
)
from .media_preview import (
    sanctuary_admin_media_panel,
)

from .helpers import (
    admin_link,
    username_link,
)


@admin.register(
    SanctuarySafetyHold
)
class SanctuarySafetyHoldAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "status_badge",
        "request_type",
        "target_link",
        "trigger_request_link",
        "supporting_request_count",
        "did_deactivate_target",
        "applied_at",
        "ended_at",
        "ended_by_link",
    )

    list_filter = (
        "status",
        "request_type",
        "did_deactivate_target",
        "applied_at",
        "ended_at",
    )

    search_fields = (
        "=id",
        "object_id",
        "reason_codes",
        "release_note",
        "=trigger_request__id",
        "ended_by__username",
    )

    ordering = (
        "-applied_at",
        "-id",
    )

    list_select_related = (
        "content_type",
        "trigger_request",
        "ended_by",
    )

    list_per_page = 50

    readonly_fields = (
        "request_type",
        "content_type",
        "object_id",
        "trigger_request",
        "supporting_requests",
        "reason_codes",
        "status",
        "previous_is_active",
        "previous_is_suspended",
        "did_deactivate_target",
        "applied_at",
        "ended_at",
        "ended_by",
        "release_note",
        "target_link",
        "target_media_preview",
        "trigger_request_link",
        "supporting_request_count",
    )

    fieldsets = (
        (
            "Safety hold",
            {
                "fields": (
                    "status",
                    "request_type",
                    "reason_codes",
                    "applied_at",
                    "ended_at",
                    "ended_by",
                    "release_note",
                ),
            },
        ),
        (
            "Target",
            {
                "fields": (
                    "content_type",
                    "object_id",
                    "target_link",
                    "target_media_preview",
                ),
            },
        ),
        (
            "Request audit",
            {
                "fields": (
                    "trigger_request",
                    "trigger_request_link",
                    "supporting_requests",
                    "supporting_request_count",
                ),
            },
        ),
        (
            "Restoration snapshot",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "previous_is_active",
                    "previous_is_suspended",
                    "did_deactivate_target",
                ),
            },
        ),
    )

    def get_queryset(
        self,
        request,
    ):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "content_type",
                "trigger_request",
                "ended_by",
            )
            .prefetch_related(
                "supporting_requests"
            )
        )

    @admin.display(
        description="Private media review",
    )
    def target_media_preview(
        self,
        obj,
    ):
        target = getattr(
            obj,
            "content_object",
            None,
        )

        if target is None:
            return "Target unavailable"

        return sanctuary_admin_media_panel(
            target
        )
    
    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_badge(
        self,
        obj,
    ):
        normalized = str(
            obj.status
            or ""
        ).lower()

        if normalized in {
            "active",
            "applied",
            "open",
        }:
            return format_html(
                '<strong style="color:#b42318;">'
                "{}"
                "</strong>",
                obj.status,
            )

        return format_html(
            '<span style="color:#667085;">'
            "{}"
            "</span>",
            obj.status,
        )

    @admin.display(
        description="Target",
    )
    def target_link(
        self,
        obj,
    ):
        return admin_link(
            getattr(
                obj,
                "content_object",
                None,
            )
        )

    @admin.display(
        description="Trigger request",
        ordering="trigger_request__id",
    )
    def trigger_request_link(
        self,
        obj,
    ):
        if not obj.trigger_request_id:
            return "-"

        return admin_link(
            obj.trigger_request,
            (
                "Sanctuary request "
                f"{obj.trigger_request_id}"
            ),
        )

    @admin.display(
        description="Supporting requests",
    )
    def supporting_request_count(
        self,
        obj,
    ):
        return (
            obj.supporting_requests.count()
        )

    @admin.display(
        description="Ended by",
        ordering="ended_by__username",
    )
    def ended_by_link(
        self,
        obj,
    ):
        return username_link(
            obj.ended_by
        )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False