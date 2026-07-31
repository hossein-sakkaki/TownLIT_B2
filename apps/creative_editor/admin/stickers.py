# apps/creative_editor/admin/stickers.py

from __future__ import annotations

from django.contrib import admin, messages
from django.db.models import Count
from django.http import HttpRequest
from django.utils.html import format_html
from django.db.models import Count, Q

from apps.creative_editor.admin.base import (
    CreativeAdminFeatureActionsMixin,
    CreativeAdminStateActionsMixin,
    admin_image_preview,
    reorder_selected_items,
)
from apps.creative_editor.models import (
    StickerAsset,
    StickerPack,
)


class StickerAssetInline(
    admin.TabularInline
):
    model = StickerAsset

    extra = 0
    show_change_link = True

    fields = (
        "small_image_preview",
        "title",
        "is_active",
        "is_featured",
        "is_converted",
        "sort_order",
    )

    readonly_fields = (
        "small_image_preview",
        "is_converted",
    )

    ordering = (
        "sort_order",
        "title",
        "id",
    )

    @admin.display(
        description="Preview",
    )
    def small_image_preview(
        self,
        obj: StickerAsset,
    ):
        if not obj or not obj.image:
            return "—"

        return admin_image_preview(
            image_field=obj.image,
            width=48,
            height=48,
            border_radius=10,
        )


@admin.register(StickerPack)
class StickerPackAdmin(
    CreativeAdminStateActionsMixin,
    CreativeAdminFeatureActionsMixin,
    admin.ModelAdmin,
):
    list_display = (
        "cover_swatch",
        "name",
        "slug",
        "is_featured",
        "is_active",
        "sort_order",
        "sticker_count",
        "available_sticker_count",
    )

    list_display_links = (
        "cover_swatch",
        "name",
    )

    list_filter = (
        "is_active",
        "is_featured",
    )

    search_fields = (
        "name",
        "slug",
        "description",
        "metadata",
    )

    ordering = (
        "sort_order",
        "name",
        "id",
    )

    list_editable = (
        "is_featured",
        "is_active",
        "sort_order",
    )

    list_per_page = 40
    save_on_top = True

    readonly_fields = (
        "public_id",
        "pack_summary",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Overview",
            {
                "fields": (
                    "pack_summary",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "name",
                    "slug",
                    "description",
                ),
            },
        ),
        (
            "Presentation",
            {
                "fields": (
                    "cover_color",
                    "is_featured",
                    "is_active",
                    "sort_order",
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
        StickerAssetInline,
    )

    actions = (
        "activate_selected",
        "deactivate_selected",
        "feature_selected",
        "unfeature_selected",
        "activate_all_stickers_in_selected_packs",
        "deactivate_all_stickers_in_selected_packs",
        "normalize_selected_sort_order",
    )

    def get_queryset(
        self,
        request,
    ):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _sticker_count=Count(
                    "stickers",
                    distinct=True,
                ),
                _available_sticker_count=Count(
                    "stickers",
                    filter=Q(
                        stickers__is_active=True,
                        stickers__is_converted=True,
                    ),
                    distinct=True,
                ),
            )
        )

    @admin.display(
        description="Cover",
    )
    def cover_swatch(
        self,
        obj: StickerPack,
    ):
        color = (
            obj.cover_color
            or "#F8F6F0"
        )

        return format_html(
            (
                '<span style="'
                'display:inline-block;'
                'width:44px;'
                'height:44px;'
                'border-radius:12px;'
                'background:{};'
                'border:1px solid rgba(0,0,0,.15);'
                'box-shadow:0 3px 9px rgba(0,0,0,.12);'
                '"></span>'
            ),
            color,
        )

    @admin.display(
        description="Stickers",
        ordering="_sticker_count",
    )
    def sticker_count(
        self,
        obj: StickerPack,
    ) -> int:
        return int(
            getattr(
                obj,
                "_sticker_count",
                0,
            )
        )

    @admin.display(
        description="Available",
        ordering="_available_sticker_count",
    )
    def available_sticker_count(
        self,
        obj: StickerPack,
    ) -> int:
        return int(
            getattr(
                obj,
                "_available_sticker_count",
                0,
            )
        )

    @admin.display(
        description="Pack Summary",
    )
    def pack_summary(
        self,
        obj: StickerPack | None,
    ):
        if not obj:
            return (
                "Save the pack to display "
                "its sticker summary."
            )

        total = obj.stickers.count()

        available = obj.stickers.filter(
            is_active=True,
            is_converted=True,
        ).count()

        return format_html(
            (
                '<div style="'
                'padding:16px;'
                'border-radius:14px;'
                'background:{};'
                'color:#111;'
                '">'
                "<strong>{}</strong><br>"
                "{} total sticker(s) · "
                "{} available"
                "</div>"
            ),
            obj.cover_color
            or "#F8F6F0",
            obj.name,
            total,
            available,
        )

    @admin.action(
        description=(
            "Activate every sticker in selected packs"
        ),
    )
    def activate_all_stickers_in_selected_packs(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = StickerAsset.objects.filter(
            pack__in=queryset,
        ).update(
            is_active=True,
        )

        self.message_user(
            request,
            f"{updated} sticker(s) activated.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description=(
            "Deactivate every sticker in selected packs"
        ),
    )
    def deactivate_all_stickers_in_selected_packs(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        updated = StickerAsset.objects.filter(
            pack__in=queryset,
        ).update(
            is_active=False,
        )

        self.message_user(
            request,
            f"{updated} sticker(s) deactivated.",
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
                f"{updated} pack(s)."
            ),
            level=messages.SUCCESS,
        )


@admin.register(StickerAsset)
class StickerAssetAdmin(
    CreativeAdminStateActionsMixin,
    CreativeAdminFeatureActionsMixin,
    admin.ModelAdmin,
):
    list_display = (
        "image_preview_small",
        "title",
        "pack",
        "dimensions_display",
        "is_active",
        "is_featured",
        "is_converted",
        "sort_order",
    )

    list_display_links = (
        "image_preview_small",
        "title",
    )

    list_filter = (
        "pack",
        "is_active",
        "is_featured",
        "is_converted",
    )

    search_fields = (
        "title",
        "slug",
        "description",
        "pack__name",
        "dominant_color",
        "metadata",
    )

    ordering = (
        "pack",
        "sort_order",
        "title",
        "id",
    )

    list_editable = (
        "is_active",
        "is_featured",
        "sort_order",
    )

    autocomplete_fields = (
        "pack",
    )

    list_select_related = (
        "pack",
    )

    list_per_page = 50
    save_on_top = True

    readonly_fields = (
        "public_id",
        "is_converted",
        "media_assets",
        "image_preview_large",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Preview",
            {
                "fields": (
                    "image_preview_large",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "pack",
                    "title",
                    "slug",
                    "description",
                ),
            },
        ),
        (
            "Sticker Image",
            {
                "fields": (
                    "image",
                    "is_converted",
                ),
            },
        ),
        (
            "Image Metadata",
            {
                "fields": (
                    "width",
                    "height",
                    "aspect_ratio",
                    "dominant_color",
                    "blurhash",
                    "media_assets",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "is_active",
                    "is_featured",
                    "sort_order",
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

    actions = (
        "activate_selected",
        "deactivate_selected",
        "feature_selected",
        "unfeature_selected",
        "normalize_selected_sort_order",
    )

    @admin.display(
        description="Preview",
    )
    def image_preview_small(
        self,
        obj: StickerAsset,
    ):
        return admin_image_preview(
            image_field=obj.image,
            width=58,
            height=58,
            border_radius=12,
        )

    @admin.display(
        description="Large Preview",
    )
    def image_preview_large(
        self,
        obj: StickerAsset | None,
    ):
        if not obj:
            return "Save the sticker to preview it."

        return admin_image_preview(
            image_field=obj.image,
            width=220,
            height=220,
            border_radius=22,
        )

    @admin.display(
        description="Dimensions",
    )
    def dimensions_display(
        self,
        obj: StickerAsset,
    ) -> str:
        if not obj.width or not obj.height:
            return "—"

        return f"{obj.width} × {obj.height}"

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
                f"{updated} sticker(s)."
            ),
            level=messages.SUCCESS,
        )