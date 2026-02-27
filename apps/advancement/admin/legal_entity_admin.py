# apps/advancement/admin/legal_entity_admin.py

from django.contrib import admin
from django.db.models import Sum, Q

from apps.advancement.models import LegalEntity
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin


@admin.register(LegalEntity, site=None)  # placeholder, registered manually below
class LegalEntityAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    list_display = (
        "name", "country", "legal_type", "base_currency", "active",
        "total_pledged_display", "total_confirmed_display"
    )
    list_filter = ("country", "legal_type", "active")
    search_fields = ("name", "registration_number", "tax_id")
    ordering = ("name",)
    actions = ("export_as_csv",)

    csv_export_fields = [
        "name", "country", "legal_type", "registration_number", "tax_id", "base_currency", "active"
    ]

    fieldsets = (
        ("Identity", {
            "fields": ("name", "country", "legal_type", "active")
        }),
        ("Registration", {
            "fields": ("registration_number", "tax_id", "effective_date")
        }),
        ("Currency", {
            "fields": ("base_currency",)
        }),
    )

    def total_pledged_display(self, obj):
        total = (
            obj.opportunities
            .filter(commitments__status__in=["PLEDGED", "CONDITIONAL", "CONFIRMED", "FULFILLED"])
            .aggregate(total=Sum("commitments__base_currency_amount"))["total"]
        )
        return total or 0
    total_pledged_display.short_description = "Total pledged"

    def total_confirmed_display(self, obj):
        total = (
            obj.opportunities
            .filter(commitments__status__in=["CONFIRMED", "FULFILLED"])
            .aggregate(total=Sum("commitments__base_currency_amount"))["total"]
        )
        return total or 0
    total_confirmed_display.short_description = "Total confirmed"