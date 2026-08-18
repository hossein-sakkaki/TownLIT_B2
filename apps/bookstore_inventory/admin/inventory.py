# apps/bookstore_inventory/admin/inventory.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin

from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin, ImmutableAdminMixin, SummaryChangeListMixin,
    WarehouseScopeAdminMixin, WorkflowAdminMixin, badge,
)
from apps.bookstore_inventory.admin.media import edition_cover_preview
from apps.bookstore_inventory.models import InventoryBalance, StockMovement


@admin.register(InventoryBalance)
class InventoryBalanceAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, SummaryChangeListMixin, WorkflowAdminMixin, admin.ModelAdmin):
    summary_fields = ("on_hand_quantity", "reserved_quantity", "unavailable_quantity")
    workflow_select_related = ("warehouse", "book_edition", "book_edition__book")
    list_display = ("cover", "warehouse", "book_edition", "on_hand_quantity", "reserved_quantity", "unavailable_quantity", "available", "health")
    list_filter = ("warehouse", "book_edition__language", "book_edition__is_active")
    search_fields = ("book_edition__edition_code", "book_edition__book__title", "book_edition__isbn", "book_edition__barcode")
    readonly_fields = ("warehouse", "book_edition", "on_hand_quantity", "reserved_quantity", "unavailable_quantity", "available", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(obj.book_edition)

    @admin.display(description="Available", ordering="on_hand_quantity")
    def available(self, obj):
        return obj.available_quantity

    @admin.display(description="Status")
    def health(self, obj):
        if obj.available_quantity < 0:
            return badge("Negative", "danger")
        if obj.available_quantity == 0:
            return badge("Out of stock", "warning")
        return badge("Available", "success")


@admin.register(StockMovement)
class StockMovementAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, ImmutableAdminMixin, SummaryChangeListMixin, WorkflowAdminMixin, admin.ModelAdmin):
    summary_fields = ("quantity", "total_amount")
    workflow_select_related = ("warehouse", "location", "book_edition", "book_edition__book", "lot", "performed_by", "inbound_shipment")
    list_display = ("performed_at", "movement_type", "warehouse", "location", "book_edition", "lot", "quantity", "unit_price", "total_amount", "reference_type", "reference_id", "performed_by")
    list_filter = ("movement_type", "warehouse", "location", "performed_at")
    search_fields = ("book_edition__edition_code", "book_edition__book__title", "lot__lot_number", "reference_type", "reference_id", "inbound_shipment__shipment_number", "notes")
    date_hierarchy = "performed_at"
