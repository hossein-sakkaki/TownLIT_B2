# apps/creative_editor/admin/compositions.py

from __future__ import annotations

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpRequest
from django.utils.html import format_html

from apps.creative_editor.admin.base import (
    admin_image_preview,
    json_pretty_payload,
)
from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)
from apps.creative_editor.services.compositions import (
    archive_composition,
    request_render,
)


class CreativeRenderJobInline(
    admin.TabularInline
):
    model = CreativeRenderJob

    extra = 1
    can_delete = False
    show_change_link = True

    fields = (
        "requested_revision",
        "status",
        "progress",
        "stage",
        "message",
        "attempt",
        "created_at",
        "finished_at",
    )

    readonly_fields = fields

    ordering = (
        "-created_at",
        "-id",
    )

    max_num = 20

    def has_add_permission(
        self,
        request,
        obj=None,
    ) -> bool:
        return False


@admin.register(CreativeComposition)
class CreativeCompositionAdmin(
    admin.ModelAdmin
):
    list_display = (
        "thumbnail_list_preview",
        "public_id",
        "owner",
        "title",
        "source_mode",
        "status",
        "visibility",
        "revision",
        "rendered_revision",
        "has_current_render_display",
        "is_active",
        "updated_at",
    )

    list_display_links = (
        "thumbnail_list_preview",
        "public_id",
        "title",
    )

    list_filter = (
        "status",
        "visibility",
        "source_mode",
        "is_active",
        "source_image_is_converted",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "public_id",
        "title",
        "owner__email",
        "owner__username",
        "document_sha256",
        "metadata",
    )

    ordering = (
        "-updated_at",
        "-id",
    )

    autocomplete_fields = (
        "owner",
    )

    raw_id_fields = (
        "source_content_type",
    )

    list_select_related = (
        "owner",
        "source_content_type",
    )

    list_per_page = 40
    save_on_top = True

    readonly_fields = (
        "public_id",
        "revision",
        "document_sha256",
        "source_image_is_converted",
        "media_assets",
        "rendered_revision",
        "rendered_at",
        "render_error",
        "source_image_preview",
        "rendered_image_preview",
        "thumbnail_preview",
        "document_preview",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Visual Overview",
            {
                "fields": (
                    "source_image_preview",
                    "rendered_image_preview",
                    "thumbnail_preview",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "owner",
                    "title",
                    "status",
                    "visibility",
                    "is_active",
                ),
            },
        ),
        (
            "Source",
            {
                "fields": (
                    "source_mode",
                    "source_image",
                    "source_image_is_converted",
                    "source_content_type",
                    "source_object_id",
                    "source_field_name",
                ),
            },
        ),
        (
            "Canvas and Document",
            {
                "fields": (
                    "canvas_width",
                    "canvas_height",
                    "format_version",
                    "revision",
                    "document_sha256",
                    "document_preview",
                    "document",
                ),
            },
        ),
        (
            "Canonical Render",
            {
                "fields": (
                    "rendered_image",
                    "thumbnail",
                    "rendered_revision",
                    "rendered_at",
                    "render_error",
                ),
            },
        ),
        (
            "Media Assets",
            {
                "fields": (
                    "media_assets",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "metadata",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    inlines = (
        CreativeRenderJobInline,
    )

    actions = (
        "request_new_render",
        "archive_selected_compositions",
    )

    @admin.display(
        description="Thumbnail",
    )
    def thumbnail_list_preview(
        self,
        obj: CreativeComposition,
    ):
        image_field = (
            obj.thumbnail
            or obj.rendered_image
            or obj.source_image
        )

        return admin_image_preview(
            image_field=image_field,
            width=54,
            height=86,
            border_radius=10,
            object_fit="cover",
        )

    @admin.display(
        description="Current Render",
        boolean=True,
    )
    def has_current_render_display(
        self,
        obj: CreativeComposition,
    ) -> bool:
        return obj.has_current_render()

    @admin.display(
        description="Source Preview",
    )
    def source_image_preview(
        self,
        obj: CreativeComposition | None,
    ):
        if not obj:
            return "—"

        return admin_image_preview(
            image_field=obj.source_image,
            width=200,
            height=350,
            border_radius=16,
        )

    @admin.display(
        description="Rendered Preview",
    )
    def rendered_image_preview(
        self,
        obj: CreativeComposition | None,
    ):
        if not obj:
            return "—"

        return admin_image_preview(
            image_field=obj.rendered_image,
            width=220,
            height=390,
            border_radius=18,
        )

    @admin.display(
        description="Thumbnail Preview",
    )
    def thumbnail_preview(
        self,
        obj: CreativeComposition | None,
    ):
        if not obj:
            return "—"

        return admin_image_preview(
            image_field=obj.thumbnail,
            width=110,
            height=195,
            border_radius=12,
        )

    @admin.display(
        description="Document Snapshot",
    )
    def document_preview(
        self,
        obj: CreativeComposition | None,
    ):
        if not obj:
            return "—"

        value = json_pretty_payload(
            obj.document or {}
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
            value,
        )

    @admin.action(
        description=(
            "Request render for current revision"
        ),
    )
    def request_new_render(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        created_count = 0
        reused_count = 0
        failed_count = 0

        for composition in queryset:
            if not composition.is_active:
                failed_count += 1
                continue

            try:
                result = request_render(
                    composition=composition,
                )

                if result.created:
                    created_count += 1
                else:
                    reused_count += 1

            except Exception:
                failed_count += 1

        level = (
            messages.SUCCESS
            if failed_count == 0
            else messages.WARNING
        )

        self.message_user(
            request,
            (
                f"Render jobs created: {created_count}. "
                f"Existing active jobs reused: {reused_count}. "
                f"Failed or skipped: {failed_count}."
            ),
            level=level,
        )

    @admin.action(
        description="Archive selected compositions",
    )
    @transaction.atomic
    def archive_selected_compositions(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        archived_count = 0
        skipped_count = 0

        for composition in queryset:
            if not composition.is_active:
                skipped_count += 1
                continue

            try:
                archive_composition(
                    composition=composition,
                )

                archived_count += 1

            except Exception:
                skipped_count += 1

        self.message_user(
            request,
            (
                f"Archived: {archived_count}. "
                f"Skipped or failed: {skipped_count}."
            ),
            level=(
                messages.SUCCESS
                if skipped_count == 0
                else messages.WARNING
            ),
        )