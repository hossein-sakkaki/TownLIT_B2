# apps/creative_editor/admin/backgrounds.py

from __future__ import annotations

from copy import deepcopy

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.creative_editor.admin.base import (
    CreativeAdminFeatureActionsMixin,
    CreativeAdminStateActionsMixin,
    json_pretty_payload,
    reorder_selected_items,
    unique_copy_key,
)
from apps.creative_editor.admin.forms import (
    CreativeBackgroundPresetAdminForm,
)
from apps.creative_editor.models import (
    CreativeBackgroundPreset,
)


@admin.register(
    CreativeBackgroundPreset
)
class CreativeBackgroundPresetAdmin(
    CreativeAdminStateActionsMixin,
    CreativeAdminFeatureActionsMixin,
    admin.ModelAdmin,
):
    form = CreativeBackgroundPresetAdminForm

    list_display = (
        "visual_swatch",
        "title",
        "key",
        "background_type",
        "family_display",
        "consumer_display",
        "is_featured",
        "is_active",
        "sort_order",
        "updated_at",
    )

    list_display_links = (
        "visual_swatch",
        "title",
    )

    list_filter = (
        "background_type",
        "is_featured",
        "is_active",
        "supported_consumers",
    )

    search_fields = (
        "title",
        "key",
        "description",
        "color",
        "colors",
        "metadata",
    )

    ordering = (
        "sort_order",
        "title",
        "id",
    )

    list_editable = (
        "is_featured",
        "is_active",
        "sort_order",
    )

    list_per_page = 50
    save_on_top = True

    readonly_fields = (
        "public_id",
        "live_visual_preview",
        "api_payload_preview",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Visual Preview",
            {
                "fields": (
                    "live_visual_preview",
                    "api_payload_preview",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "key",
                    "title",
                    "description",
                ),
            },
        ),
        (
            "Background Design",
            {
                "fields": (
                    "background_type",
                    "color",
                    "colors",
                    "angle",
                ),
                "description": (
                    "Choose Solid Color or Gradient. "
                    "The preview updates as values change."
                ),
            },
        ),
        (
            "Availability",
            {
                "fields": (
                    "supported_consumers",
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

    actions = (
        "activate_selected",
        "deactivate_selected",
        "feature_selected",
        "unfeature_selected",
        "duplicate_selected",
        "normalize_selected_sort_order",
    )

    class Media:
        css = {
            "all": (
                "creative_editor/admin/"
                "background_admin.css",
            ),
        }

        js = (
            "creative_editor/admin/"
            "background_admin.js",
        )

    @admin.display(
        description="Preview",
    )
    def visual_swatch(
        self,
        obj: CreativeBackgroundPreset,
    ):
        style = self._background_css(
            obj
        )

        return format_html(
            (
                '<div class="creative-background-list-preview" '
                'style="{}">'
                '<span>{}</span>'
                "</div>"
            ),
            style,
            "★" if obj.is_featured else "",
        )

    @admin.display(
        description="Live Preview",
    )
    def live_visual_preview(
        self,
        obj: CreativeBackgroundPreset | None,
    ):
        style = (
            self._background_css(obj)
            if obj
            else (
                "background:#0F52BA;"
            )
        )

        return format_html(
            (
                '<div class="creative-background-preview-shell">'
                '<div id="creative-background-live-preview" '
                'class="creative-background-live-preview" '
                'style="{}">'
                '<div class="creative-background-preview-overlay">'
                "<strong>TownLIT</strong>"
                "<span>Creative Background Preview</span>"
                "</div>"
                "</div>"
                '<div id="creative-background-preview-values" '
                'class="creative-background-preview-values">'
                "</div>"
                "</div>"
            ),
            style,
        )

    @admin.display(
        description="iOS / Document Payload",
    )
    def api_payload_preview(
        self,
        obj: CreativeBackgroundPreset | None,
    ):
        payload = (
            obj.as_document_background()
            if obj
            else {
                "type": "color",
                "color": "#0F52BAFF",
            }
        )

        pretty = json_pretty_payload(
            payload
        )

        return format_html(
            (
                '<pre class="creative-background-json-preview">'
                "{}"
                "</pre>"
            ),
            pretty,
        )

    @admin.display(
        description="Family",
    )
    def family_display(
        self,
        obj: CreativeBackgroundPreset,
    ) -> str:
        metadata = (
            obj.metadata
            if isinstance(
                obj.metadata,
                dict,
            )
            else {}
        )

        return str(
            metadata.get(
                "family",
                "—",
            )
        )

    @admin.display(
        description="Consumers",
    )
    def consumer_display(
        self,
        obj: CreativeBackgroundPreset,
    ):
        consumers = (
            obj.supported_consumers
            if isinstance(
                obj.supported_consumers,
                list,
            )
            else []
        )

        if not consumers:
            return mark_safe(
                '<span class="creative-consumer-badge">'
                "All"
                "</span>"
            )

        return format_html(
            "{}",
            ", ".join(consumers),
        )

    @admin.action(
        description="Duplicate selected backgrounds",
    )
    @transaction.atomic
    def duplicate_selected(
        self,
        request: HttpRequest,
        queryset,
    ) -> None:
        created_count = 0

        for source in queryset.order_by(
            "sort_order",
            "id",
        ):
            duplicate = (
                CreativeBackgroundPreset(
                    key=unique_copy_key(
                        model=(
                            CreativeBackgroundPreset
                        ),
                        source_key=source.key,
                    ),
                    title=f"{source.title} Copy",
                    description=source.description,
                    background_type=(
                        source.background_type
                    ),
                    color=source.color,
                    colors=deepcopy(
                        source.colors
                    ),
                    angle=source.angle,
                    supported_consumers=deepcopy(
                        source.supported_consumers
                    ),
                    metadata=deepcopy(
                        source.metadata
                    ),
                    is_featured=False,
                    is_active=False,
                    sort_order=(
                        source.sort_order + 1
                    ),
                )
            )

            duplicate.full_clean()
            duplicate.save()

            created_count += 1

        self.message_user(
            request,
            (
                f"{created_count} background(s) duplicated. "
                "Copies were created inactive."
            ),
            level=messages.SUCCESS,
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
            start=10,
            step=10,
        )

        self.message_user(
            request,
            (
                f"Sort order normalized for "
                f"{updated} background(s)."
            ),
            level=messages.SUCCESS,
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ) -> None:
        obj.full_clean()

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @staticmethod
    def _background_css(
        obj: CreativeBackgroundPreset | None,
    ) -> str:
        if not obj:
            return "background:#0F52BA;"

        if (
            obj.background_type
            == CreativeBackgroundPreset
            .BackgroundType
            .COLOR
        ):
            return (
                f"background:{obj.color or '#0F52BAFF'};"
            )

        colors = (
            obj.colors
            if isinstance(
                obj.colors,
                list,
            )
            else []
        )

        if len(colors) < 2:
            colors = [
                "#071A33FF",
                "#0F52BAFF",
            ]

        normalized_colors = ", ".join(
            colors
        )

        return (
            "background:"
            f"linear-gradient({obj.angle}deg,"
            f"{normalized_colors});"
        )