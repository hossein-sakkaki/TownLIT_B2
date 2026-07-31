# apps/creative_editor/admin/render_jobs.py

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from apps.creative_editor.admin.base import (
    json_pretty_payload,
)
from apps.creative_editor.models import (
    CreativeRenderJob,
)


@admin.register(CreativeRenderJob)
class CreativeRenderJobAdmin(
    admin.ModelAdmin
):
    list_display = (
        "status_indicator",
        "public_id",
        "composition",
        "requested_revision",
        "status",
        "progress_display",
        "stage",
        "attempt",
        "queue",
        "created_at",
        "finished_at",
    )

    list_display_links = (
        "status_indicator",
        "public_id",
    )

    list_filter = (
        "status",
        "queue",
        "stage",
        "created_at",
        "finished_at",
    )

    search_fields = (
        "public_id",
        "composition__public_id",
        "composition__title",
        "composition__owner__email",
        "composition__owner__username",
        "task_id",
        "document_sha256",
        "message",
        "error",
    )

    ordering = (
        "-created_at",
        "-id",
    )

    autocomplete_fields = (
        "composition",
    )

    list_select_related = (
        "composition",
        "composition__owner",
    )

    list_per_page = 50

    readonly_fields = (
        "public_id",
        "composition",
        "requested_revision",
        "document_snapshot_preview",
        "document_snapshot",
        "document_sha256",
        "status",
        "progress",
        "stage",
        "message",
        "error",
        "task_id",
        "queue",
        "output_path",
        "thumbnail_path",
        "attempt",
        "max_attempts",
        "heartbeat_at",
        "started_at",
        "finished_at",
        "duration_ms",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "composition",
                    "requested_revision",
                    "document_sha256",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "progress",
                    "stage",
                    "message",
                    "error",
                ),
            },
        ),
        (
            "Celery",
            {
                "fields": (
                    "task_id",
                    "queue",
                    "attempt",
                    "max_attempts",
                    "heartbeat_at",
                ),
            },
        ),
        (
            "Output",
            {
                "fields": (
                    "output_path",
                    "thumbnail_path",
                ),
            },
        ),
        (
            "Document Snapshot",
            {
                "fields": (
                    "document_snapshot_preview",
                    "document_snapshot",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Timing",
            {
                "fields": (
                    "started_at",
                    "finished_at",
                    "duration_ms",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="",
    )
    def status_indicator(
        self,
        obj: CreativeRenderJob,
    ):
        color_map = {
            "queued": "#F4A429",
            "processing": "#0F52BA",
            "done": "#3BAA75",
            "failed": "#C40233",
            "canceled": "#6F6F6F",
        }

        color = color_map.get(
            obj.status,
            "#6F6F6F",
        )

        return format_html(
            (
                '<span style="'
                'display:inline-block;'
                'width:13px;'
                'height:13px;'
                'border-radius:50%;'
                'background:{};'
                'box-shadow:0 0 0 4px {}22;'
                '"></span>'
            ),
            color,
            color,
        )

    @admin.display(
        description="Progress",
        ordering="progress",
    )
    def progress_display(
        self,
        obj: CreativeRenderJob,
    ):
        value = max(
            0,
            min(
                int(obj.progress or 0),
                100,
            ),
        )

        return format_html(
            (
                '<div style="'
                'width:110px;'
                'height:12px;'
                'background:#e5e7eb;'
                'border-radius:8px;'
                'overflow:hidden;'
                '">'
                '<div style="'
                'width:{}%;'
                'height:100%;'
                'background:#0F52BA;'
                '"></div>'
                "</div>"
                '<small style="display:block;margin-top:3px;">'
                "{}%"
                "</small>"
            ),
            value,
            value,
        )

    @admin.display(
        description="Readable Document Snapshot",
    )
    def document_snapshot_preview(
        self,
        obj: CreativeRenderJob | None,
    ):
        if not obj:
            return "—"

        pretty = json_pretty_payload(
            obj.document_snapshot or {}
        )

        return format_html(
            (
                '<pre style="'
                'max-height:420px;'
                'overflow:auto;'
                'padding:14px;'
                'border-radius:12px;'
                'background:#111827;'
                'color:#e5e7eb;'
                'font-size:12px;'
                'line-height:1.5;'
                '">'
                "{}"
                "</pre>"
            ),
            pretty,
        )

    def has_add_permission(
        self,
        request,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ) -> bool:
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ) -> bool:
        if obj is not None:
            return False

        return super().has_change_permission(
            request,
            obj,
        )