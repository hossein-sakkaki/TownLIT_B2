# apps/bookstore_inventory/admin/warehouse.py

from django.contrib import admin

from apps.bookstore_inventory.models import Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    # Warehouse admin
    list_display = ("name", "code", "city", "province_state", "country", "is_active", "balance_count")
    search_fields = (
        "name",
        "code",
        "city",
        "province_state",
        "postal_code",
        "contact_name",
        "contact_phone",
    )
    list_filter = ("is_active", "country", "province_state")
    readonly_fields = ("created_at", "updated_at", "full_address_display")
    fieldsets = (
        ("Main", {
            "fields": ("name", "code", "is_active")
        }),
        ("Address", {
            "fields": (
                "address_line_1",
                "address_line_2",
                "city",
                "province_state",
                "postal_code",
                "country",
                "full_address_display",
            )
        }),
        ("Contact", {
            "fields": ("contact_name", "contact_phone")
        }),
        ("Notes", {
            "fields": ("description",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def balance_count(self, obj):
        # Count balances
        return obj.balances.count()

    balance_count.short_description = "Balances"

    def full_address_display(self, obj):
        # Display built address
        return obj.full_address or "-"

    full_address_display.short_description = "Full address"