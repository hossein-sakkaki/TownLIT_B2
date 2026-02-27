# apps/advancement/admin/scoring_admin.py

from django.contrib import admin

from apps.advancement.models import StrategicScore
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin


class StrategicScoreAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    """Admin for strategic scoring of external entities."""

    list_display = (
        "external_entity",
        "mission_alignment",
        "funding_capacity",
        "access_level",
        "influence_value",
        "effort_required",
        "total_score_display",
        "updated_at",
    )
    list_select_related = ("external_entity",)
    search_fields = ("external_entity__name",)
    actions = ("export_as_csv",)

    csv_export_fields = [
        "external_entity",
        "mission_alignment",
        "funding_capacity",
        "access_level",
        "influence_value",
        "effort_required",
        "notes",
        "updated_at",
    ]

    readonly_fields = ("updated_at",)

    def get_fieldsets(self, request, obj=None):
        """Show system fields only on change form."""
        base = (
            ("Target", {"fields": ("external_entity",)}),
            ("Scoring", {
                "fields": (
                    "mission_alignment",
                    "funding_capacity",
                    "access_level",
                    "influence_value",
                    "effort_required",
                )
            }),
            ("Notes", {"fields": ("notes",)}),
        )

        if obj is None:
            return base

        return base + (
            ("System", {"fields": ("updated_at",)}),
        )

    def total_score_display(self, obj):
        return obj.total_score

    total_score_display.short_description = "Total Score"