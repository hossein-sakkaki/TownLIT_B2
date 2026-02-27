# apps/advancement/admin/interaction_admin.py

from django.contrib import admin

from apps.advancement.models import InteractionLog
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin
from .filters import InteractionFollowUpFilter
from .actions import mark_interactions_done


class InteractionLogAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    """Admin for outreach/follow-up interactions."""

    list_display = (
        "external_entity",
        "interaction_type",
        "status",
        "subject",
        "occurred_at",
        "next_action_date",
        "assigned_to",
        "created_at",
    )
    list_filter = ("interaction_type", "status", "occurred_at", "next_action_date", InteractionFollowUpFilter)
    search_fields = ("external_entity__name", "subject", "summary", "next_action")
    list_select_related = ("external_entity", "assigned_to", "created_by")
    actions = ("export_as_csv", "mark_interactions_done")

    csv_export_fields = [
        "external_entity__name",
        "interaction_type",
        "status",
        "subject",
        "summary",
        "occurred_at",
        "next_action",
        "next_action_date",
        "assigned_to",
        "created_by",
        "created_at",
    ]

    readonly_fields = ("created_at",)

    def get_fieldsets(self, request, obj=None):
        """Hide system fields on add form."""
        base = (
            ("Target", {"fields": ("external_entity",)}),
            ("Interaction", {"fields": ("interaction_type", "status", "subject", "summary")}),
            ("Timing", {"fields": ("occurred_at", "next_action", "next_action_date")}),
            ("Assignment", {"fields": ("assigned_to", "created_by")}),
        )

        if obj is None:
            return base

        return base + (
            ("System", {"fields": ("created_at",)}),
        )

    @admin.action(description="Mark selected interactions as Done")
    def mark_interactions_done(self, request, queryset):
        return mark_interactions_done(self, request, queryset)