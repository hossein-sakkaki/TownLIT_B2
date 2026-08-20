# apps/communication/admin/design.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.communication.forms import (
    EmailTemplateAdminForm,
    EmailTemplateBlockAdminForm,
    EmailThemeAdminForm,
)
from apps.communication.models import (
    EmailTemplate,
    EmailTemplateBlock,
    EmailTheme,
)


class EmailTemplateBlockInline(admin.StackedInline):
    model = EmailTemplateBlock
    form = EmailTemplateBlockAdminForm
    extra = 0
    fields = (
        "block_type",
        "name",
        "sort_order",
        "is_enabled",
        "headline",
        "content",
        "secondary_content",
        "image_url",
        "image_alt",
        "action_label",
        "action_url",
        "attribution",
        "alignment",
        "spacer_height",
        "social_links",
        "custom_html",
    )


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    form = EmailTemplateAdminForm
    inlines = [EmailTemplateBlockInline]

    list_display = (
        "name",
        "category",
        "editor_mode",
        "layout",
        "theme",
        "is_active",
        "is_system",
        "version",
        "preview_link",
        "updated_at",
    )
    list_filter = (
        "category",
        "editor_mode",
        "layout",
        "is_active",
        "is_system",
        "is_locked",
    )
    search_fields = (
        "name",
        "subject_template",
        "description",
    )
    autocomplete_fields = ("theme",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Template",
            {
                "fields": (
                    "name",
                    "description",
                    "category",
                    "editor_mode",
                    "is_active",
                ),
            },
        ),
        (
            "Message",
            {
                "fields": (
                    "subject_template",
                    "preheader_template",
                    "body_template",
                ),
            },
        ),
        (
            "Design",
            {
                "fields": (
                    "layout",
                    "theme",
                ),
            },
        ),
        (
            "Advanced",
            {
                "fields": (
                    "default_context",
                    "is_system",
                    "is_locked",
                    "version",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if obj and (obj.is_system or obj.campaigns.exists()):
            return False

        return super().has_delete_permission(request, obj)

    @admin.display(description="Preview")
    def preview_link(self, obj):
        url = reverse(
            "communication:email-template-preview",
            args=[obj.pk],
        )

        return format_html(
            '<a href="{}" target="_blank">Preview</a>',
            url,
        )


@admin.register(EmailTheme)
class EmailThemeAdmin(admin.ModelAdmin):
    form = EmailThemeAdminForm

    list_display = (
        "name",
        "layout",
        "accent_preview",
        "content_width",
        "is_default",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "layout",
        "is_default",
        "is_active",
    )
    search_fields = (
        "name",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Theme",
            {
                "fields": (
                    "name",
                    "description",
                    "layout",
                    "logo_url",
                    "is_active",
                    "is_default",
                ),
            },
        ),
        (
            "Colors",
            {
                "fields": (
                    "background_color",
                    "surface_color",
                    "text_color",
                    "heading_color",
                    "accent_color",
                    "secondary_accent_color",
                    "muted_color",
                    "button_text_color",
                ),
            },
        ),
        (
            "Layout",
            {
                "fields": (
                    "font_family",
                    "content_width",
                    "border_radius",
                ),
            },
        ),
        (
            "Advanced",
            {
                "fields": (
                    "style_config",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Accent")
    def accent_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:44px;height:20px;'
            'border-radius:5px;background:{};border:1px solid #bbb;"></span>',
            obj.accent_color,
        )