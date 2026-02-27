# apps/advancement/admin/commitment_admin.py

from django.contrib import admin

from apps.advancement.models import Commitment
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin
from .actions import mark_commitments_confirmed, mark_commitments_fulfilled


class CommitmentInline(admin.TabularInline):
    """Inline commitments under opportunity."""
    model = Commitment
    extra = 0
    fields = (
        "commitment_date",
        "status",
        "committed_amount",
        "currency",
        "exchange_rate_snapshot",
        "base_currency_amount",
        "conditions",
    )
    show_change_link = True


class CommitmentAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    """Admin for pledges/commitments."""

    list_display = (
        "opportunity",
        "status",
        "committed_amount",
        "currency",
        "base_currency_amount",
        "commitment_date",
        "created_at",
    )
    list_filter = ("status", "currency", "commitment_date")
    search_fields = ("opportunity__title", "opportunity__external_entity__name", "notes", "conditions")
    list_select_related = ("opportunity", "opportunity__external_entity")
    actions = (
        "export_as_csv",
        "mark_commitments_confirmed",
        "mark_commitments_fulfilled",
    )

    csv_export_fields = [
        "opportunity__title",
        "opportunity__external_entity__name",
        "opportunity__legal_entity__name",
        "status",
        "committed_amount",
        "currency",
        "exchange_rate_snapshot",
        "base_currency_amount",
        "commitment_date",
        "conditions",
        "notes",
        "created_at",
    ]

    readonly_fields = ("created_at",)

    def get_fieldsets(self, request, obj=None):
        """Hide system fields on add form."""
        base = (
            ("Opportunity", {"fields": ("opportunity",)}),
            ("Commitment", {
                "fields": (
                    "status",
                    "committed_amount",
                    "currency",
                    "exchange_rate_snapshot",
                    "base_currency_amount",
                    "commitment_date",
                )
            }),
            ("Details", {"fields": ("conditions", "notes")}),
        )

        if obj is None:
            return base

        return base + (
            ("System", {"fields": ("created_at",)}),
        )

    @admin.action(description="Mark selected commitments as Confirmed")
    def mark_commitments_confirmed(self, request, queryset):
        return mark_commitments_confirmed(self, request, queryset)

    @admin.action(description="Mark selected commitments as Fulfilled")
    def mark_commitments_fulfilled(self, request, queryset):
        return mark_commitments_fulfilled(self, request, queryset)