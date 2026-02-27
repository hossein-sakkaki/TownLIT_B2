# apps/advancement/admin/external_entity_admin.py

from django.contrib import admin
from django.utils.html import format_html

from apps.advancement.models import ExternalEntity, InteractionLog
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin
from .filters import HighStrategicScoreFilter


class InteractionInline(admin.TabularInline):
    """Recent interactions inline."""
    model = InteractionLog
    extra = 0
    fields = ("interaction_type", "status", "subject", "occurred_at", "next_action_date", "assigned_to")
    show_change_link = True


class ExternalEntityAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    """Admin for external entities."""

    list_display = (
        "name",
        "entity_type",
        "country",
        "region",
        "denomination",
        "primary_email",
        "is_active",
        "strategic_score_badge",
        "created_at",
    )
    list_filter = ("entity_type", "country", "is_active", "denomination", "tags", HighStrategicScoreFilter)
    search_fields = ("name", "primary_email", "website", "description", "notes_private")
    filter_horizontal = ("tags",)
    inlines = [InteractionInline]
    actions = ("export_as_csv",)

    csv_export_fields = [
        "name", "entity_type", "country", "region", "denomination",
        "primary_email", "primary_phone", "website", "is_active", "created_at",
    ]

    readonly_fields = ("created_at", "updated_at")

    # IMPORTANT: no static fieldsets with created_at for add form
    def get_fieldsets(self, request, obj=None):
        base = (
            ("Identity", {"fields": ("name", "entity_type", "is_active")}),
            ("Geography", {"fields": ("country", "region")}),
            ("Faith / Network", {"fields": ("denomination",)}),
            ("Contact", {"fields": ("primary_email", "primary_phone", "address", "website")}),
            ("Classification", {"fields": ("tags",)}),
            ("Notes", {"fields": ("description", "notes_private")}),
        )
        if obj is None:
            return base

        return base + (
            ("System", {"fields": ("created_at", "updated_at")}),
        )

    def get_inline_instances(self, request, obj=None):
        """Hide inlines on add form."""
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def strategic_score_badge(self, obj):
        """Show score badge if score exists."""
        if not hasattr(obj, "strategic_score"):
            return format_html('<span style="color:#64748b;">No score</span>')

        score = getattr(obj.strategic_score, "total_score", None)
        if score is None:
            return format_html('<span style="color:#64748b;">No score</span>')

        if score >= 20:
            bg = "#16a34a"
        elif score >= 12:
            bg = "#f59e0b"
        else:
            bg = "#dc2626"

        return format_html(
            '<span style="padding:2px 8px;border-radius:999px;color:white;background:{};">{}</span>',
            bg, score
        )

    strategic_score_badge.short_description = "Strategic Score"