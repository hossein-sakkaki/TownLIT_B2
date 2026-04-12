# apps/bookstore_inventory/admin/inventory.py

from django.contrib import admin
from django.utils.html import format_html

from apps.bookstore_inventory.models import InventoryBalance, StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    # Stock movement admin
    list_display = (
        "performed_at",
        "movement_type",
        "warehouse",
        "book_edition",
        "quantity",
        "reference_type",
        "reference_id",
        "performed_by",
    )
    search_fields = (
        "book_edition__book__title",
        "book_edition__edition_code",
        "book_edition__barcode",
        "reference_type",
        "reference_id",
        "notes",
    )
    list_filter = ("movement_type", "warehouse", "performed_at")
    autocomplete_fields = ("warehouse", "book_edition", "inbound_shipment", "performed_by")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "performed_at"


@admin.register(InventoryBalance)
class InventoryBalanceAdmin(admin.ModelAdmin):
    # Inventory balance admin
    list_display = (
        "warehouse",
        "book_edition",
        "on_hand_quantity",
        "reserved_quantity",
        "available_quantity_display",
        "stock_status",
    )
    search_fields = (
        "warehouse__name",
        "book_edition__book__title",
        "book_edition__edition_code",
        "book_edition__barcode",
    )
    list_filter = ("warehouse",)
    autocomplete_fields = ("warehouse", "book_edition")
    readonly_fields = (
        "created_at",
        "updated_at",
        "available_quantity_display",
        "stock_status",
    )

    def available_quantity_display(self, obj):
        # Display available stock
        return obj.available_quantity

    available_quantity_display.short_description = "Available"

    def stock_status(self, obj):
        # Display stock status
        qty = obj.available_quantity
        if qty <= 0:
            return format_html('<span style="color:#b91c1c;font-weight:600;">Out of stock</span>')
        if qty <= 5:
            return format_html('<span style="color:#b45309;font-weight:600;">Low stock</span>')
        return format_html('<span style="color:#15803d;font-weight:600;">In stock</span>')

    stock_status.short_description = "Status"