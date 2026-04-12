# apps/bookstore_inventory/admin/finance.py

from django.contrib import admin

from apps.bookstore_inventory.admin.mixins import LedgerSummaryMixin
from apps.bookstore_inventory.models import CashLedgerEntry


@admin.register(CashLedgerEntry)
class CashLedgerEntryAdmin(LedgerSummaryMixin, admin.ModelAdmin):
    # Cash ledger admin
    list_display = (
        "entry_date",
        "direction",
        "entry_type",
        "amount",
        "currency",
        "reference_type",
        "reference_id",
        "recorded_by",
    )
    # change_list_template = "admin/bookstore_inventory/change_list_with_summary.html"
    search_fields = ("reference_type", "reference_id", "notes")
    list_filter = ("direction", "entry_type", "currency", "entry_date")
    autocomplete_fields = ("recorded_by",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "ledger_summary",
    )
    date_hierarchy = "entry_date"
    fieldsets = (
        ("Main", {
            "fields": (
                "direction",
                "entry_type",
                "amount",
                "currency",
                "entry_date",
            )
        }),
        ("Reference", {
            "fields": (
                "reference_type",
                "reference_id",
            )
        }),
        ("Notes", {
            "fields": (
                "notes",
                "recorded_by",
                "ledger_summary",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def ledger_summary(self, obj):
        # Show total balance summary
        totals = self.get_ledger_totals()
        return (
            f"Total in: {totals['total_in']} | "
            f"Total out: {totals['total_out']} | "
            f"Net: {totals['net']}"
        )

    ledger_summary.short_description = "Ledger summary"

    def changelist_view(self, request, extra_context=None):
        # Add quick summary to changelist
        extra_context = extra_context or {}
        totals = self.get_ledger_totals()
        extra_context["summary_data_verbose"] = {
            "Total in": totals["total_in"],
            "Total out": totals["total_out"],
            "Net balance": totals["net"],
        }
        return super().changelist_view(request, extra_context=extra_context)