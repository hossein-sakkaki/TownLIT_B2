# apps/bookstore_inventory/admin/finance.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin

from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin,
    SummaryChangeListMixin,
    WorkflowAdminMixin,
    badge,
)
from apps.bookstore_inventory.models import CashLedgerEntry
from apps.bookstore_inventory.services.reports import (
    scoped_cash_ledger_queryset,
)


@admin.register(CashLedgerEntry)
class CashLedgerEntryAdmin(
    HiddenFromAdminIndexMixin,
    SummaryChangeListMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True

    summary_fields = ("amount",)
    workflow_select_related = ("recorded_by",)

    list_display = (
        "entry_date",
        "direction_badge",
        "entry_type",
        "amount",
        "currency",
        "reference_type",
        "reference_id",
        "recorded_by",
    )
    list_filter = (
        "direction",
        "entry_type",
        "currency",
        "entry_date",
    )
    search_fields = (
        "reference_type",
        "reference_id",
        "notes",
    )
    autocomplete_fields = ("recorded_by",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    date_hierarchy = "entry_date"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        allowed_ids = scoped_cash_ledger_queryset(
            request.user
        ).values_list(
            "pk",
            flat=True,
        )

        return queryset.filter(
            pk__in=allowed_ids
        )

    @admin.display(
        description="Direction",
        ordering="direction",
    )
    def direction_badge(self, obj):
        return badge(
            obj.get_direction_display(),
            (
                "success"
                if obj.direction == "in"
                else "danger"
            ),
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return tuple(
                field.name
                for field in self.model._meta.fields
            )

        return super().get_readonly_fields(
            request,
            obj,
        )