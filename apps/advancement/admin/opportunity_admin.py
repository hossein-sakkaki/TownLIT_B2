# apps/advancement/admin/opportunity_admin.py

from django.contrib import admin
from django.utils.html import format_html

from apps.advancement.models import Opportunity
from .commitment_admin import CommitmentInline
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin
from .filters import OpportunityPipelineFilter, OpportunityDeadlineStatusFilter
from .actions import mark_opportunities_under_review, mark_opportunities_closed


class OpportunityAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    """Admin for funding/partnership opportunities."""

    list_display = (
        "title",
        "external_entity",
        "legal_entity",
        "opportunity_type",
        "stage_badge",
        "currency",
        "amount_requested",
        "expected_amount",
        "deadline",
        "probability_score",
        "is_active",
    )
    list_filter = (
        "stage",
        "opportunity_type",
        "currency",
        "legal_entity",
        "tags",
        OpportunityPipelineFilter,
        OpportunityDeadlineStatusFilter,
    )
    search_fields = ("title", "external_entity__name", "notes")
    list_select_related = ("external_entity", "legal_entity")
    filter_horizontal = ("tags",)
    inlines = [CommitmentInline]
    actions = (
        "export_as_csv",
        "mark_opportunities_under_review",
        "mark_opportunities_closed",
    )

    csv_export_fields = [
        "title",
        "external_entity__name",
        "legal_entity__name",
        "opportunity_type",
        "stage",
        "currency",
        "amount_requested",
        "expected_amount",
        "deadline",
        "submission_date",
        "decision_date",
        "probability_score",
        "notes",
    ]

    readonly_fields = ("created_at", "updated_at", "is_active")

    def get_fieldsets(self, request, obj=None):
        """Show system fields only on change form."""
        base = (
            ("Core", {
                "fields": (
                    "title",
                    "external_entity",
                    "legal_entity",
                    "opportunity_type",
                    "stage",
                )
            }),
            ("Funding", {
                "fields": (
                    "currency",
                    "amount_requested",
                    "expected_amount",
                    "probability_score",
                )
            }),
            ("Dates", {
                "fields": ("deadline", "submission_date", "decision_date")
            }),
            ("Classification", {
                "fields": ("tags",)
            }),
            ("Notes", {
                "fields": ("notes",)
            }),
        )

        if obj is None:
            return base

        return base + (
            ("System", {
                "fields": ("is_active", "created_at", "updated_at")
            }),
        )

    def get_inline_instances(self, request, obj=None):
        """Hide commitments inline on add form."""
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    @admin.action(description="Mark selected as Under Review")
    def mark_opportunities_under_review(self, request, queryset):
        return mark_opportunities_under_review(self, request, queryset)

    @admin.action(description="Mark selected as Closed")
    def mark_opportunities_closed(self, request, queryset):
        return mark_opportunities_closed(self, request, queryset)

    def stage_badge(self, obj):
        """Colored stage badge."""
        color_map = {
            "PROSPECT": "#64748b",
            "LOI": "#2563eb",
            "SUBMITTED": "#7c3aed",
            "UNDER_REVIEW": "#f59e0b",
            "APPROVED": "#16a34a",
            "DECLINED": "#dc2626",
            "CLOSED": "#334155",
        }
        color = color_map.get(obj.stage, "#475569")
        label = obj.get_stage_display()
        return format_html(
            '<span style="padding:2px 8px;border-radius:999px;color:white;background:{};">{}</span>',
            color,
            label,
        )

    stage_badge.short_description = "Stage"