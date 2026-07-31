# apps/creative_editor/admin/fonts.py

from __future__ import annotations

from django.contrib import admin, messages
from django.http import HttpRequest
from django.utils.html import format_html

from apps.creative_editor.admin.base import (
    CreativeAdminStateActionsMixin,
    reorder_selected_items,
)
from apps.creative_editor.models import (
    CreativeFont,
)


@admin.register(CreativeFont)
class CreativeFontAdmin(
    CreativeAdminStateActionsMixin,
    admin.ModelAdmin,
):
    list_display = (
        "font_preview",
        "display_name",
        "key",
        "category",
        "source",
        "supports_ltr",
        "supports_rtl",
        "supports_bold",
        "supports_italic",
        "is_active",
        "sort_order",
    )

    list_display_links = (
        "font_preview",
        "display_name",
    )

    list_filter = (
        "is_active",
        "category",
        "source",
        "supports_ltr",
        "supports_rtl",
        "supports_bold",
        "supports_italic",
    )

    search_fields = (
        "display_name",
        "key",
        "postscript_name",
        "preview_text",
        "license_reference",
    )

    ordering = (
        "sort_order",
        "display_name",
        "id",
    )

    list_editable = (
        "is_active",
        "sort_order",
    )

    list_per_page = 50
    save_on_top = True

    readonly_fields = (
        "public_id",
        "font_detail_preview",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Preview",
            {
                "fields": (
                    "font_detail_preview",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "key",
                    "display_name",
                    "postscript_name",
                    "category",
                    "source",
                ),
            },
        ),
        (
            "Language Support",
            {
                "fields": (
                    "supports_ltr",
                    "supports_rtl",
                    "supports_bold",
                    "supports_italic",
                ),
            },
        ),
        (
            "Presentation",
            {
                "fields": (
                    "minimum_size",
                    "maximum_size",
                    "preview_text",
                    "sort_order",
                    "is_active",
                ),
            },
        ),
        (
            "License and Metadata",
            {
                "fields": (
                    "license_reference",
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

    actions = (
        "activate_selected",
        "deactivate_selected",
        "enable_rtl_support",
        "disable_rtl_support",
        "normalize_selected_sort_order",
    )

    @admin.display(
        description="Preview",
    )
    def font_preview(
        self,
        obj: CreativeFont,
    ):
        text = (
            obj.preview_text.strip()
            or obj.display_name
        )

        font_family = (
            obj.postscript_name.strip()
            or "inherit"
        )

        return format_html(
            (
                '<span style="'
                'display:inline-block;'
                'min-width:160px;'
                'font-family:\'{}\';'
                'font-size:18px;'
                'line-height:1.35;'
                'padding:7px 10px;'
                'border-radius:9px;'
                'background:#f7f7f7;'
                'border:1px solid #ddd;'
                '">'
                "{}"
                "</span>"
            ),
            font_family,
            text[:48],
        )

    @admin.display(
        description="Font Preview",
    )
    def font_detail_preview(
        self,
        obj: CreativeFont | None,
    ):
        if not obj:
            return (
                "Save the font to display "
                "its configured preview."
            )

        preview_text = (
            obj.preview_text.strip()
            or (
                "TownLIT · Journey · "
                "Faith, Hope and Love"
            )
        )

        family = (
            obj.postscript_name.strip()
            or "inherit"
        )

        return format_html(
            (
                '<div style="'
                'font-family:\'{}\';'
                'padding:24px;'
                'border-radius:16px;'
                'background:linear-gradient('
                '135deg,#071A33,#0F52BA);'
                'color:white;'
                'font-size:34px;'
                'line-height:1.35;'
                '">'
                "{}"
                "</div>"
            ),
            family,
            preview_text,
        )

    @admin.action(
        description="Enable RTL support",
    )
    def enable_rtl_support(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = queryset.update(
            supports_rtl=True,
        )

        self.message_user(
            request,
            f"RTL enabled for {updated} font(s).",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Disable RTL support",
    )
    def disable_rtl_support(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = queryset.update(
            supports_rtl=False,
        )

        self.message_user(
            request,
            f"RTL disabled for {updated} font(s).",
            level=messages.WARNING,
        )

    @admin.action(
        description=(
            "Normalize selected sort order "
            "(10, 20, 30...)"
        ),
    )
    def normalize_selected_sort_order(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = reorder_selected_items(
            queryset=queryset,
        )

        self.message_user(
            request,
            (
                f"Sort order normalized for "
                f"{updated} font(s)."
            ),
            level=messages.SUCCESS,
        )