from django.contrib import admin
from .models import Warehouse, WarehouseInventory, StockMovement, TemporaryReservation
from django.utils import timezone





# WAREHOUSE Admin -------------------------------------------------------------------
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'location', 'is_temporarily_closed', 'is_active', 'created_at', 'updated_at')
    list_filter = ('store', 'is_temporarily_closed', 'is_active')
    search_fields = ('name', 'store__name', 'location')
    actions = ['mark_as_active', 'mark_as_inactive', 'mark_as_temporarily_closed']

    @admin.action(description="Mark selected warehouses as active")
    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True, is_temporarily_closed=False)

    @admin.action(description="Mark selected warehouses as inactive")
    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Mark selected warehouses as temporarily closed")
    def mark_as_temporarily_closed(self, request, queryset):
        queryset.update(is_temporarily_closed=True)


# WAREHOUSE INVENTORY Admin ----------------------------------------------------------
@admin.register(WarehouseInventory)
class WarehouseInventoryAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'product', 'quantity', 'reserved_quantity', 'last_updated', 'is_active')
    list_filter = ('warehouse', 'product', 'is_active')
    search_fields = ('warehouse__name', 'product__product_name')
    actions = ['mark_as_active', 'mark_as_inactive']

    @admin.action(description="Mark selected inventories as active")
    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Mark selected inventories as inactive")
    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)


# STOCK MOVEMENT Admin ----------------------------------------------------------------
@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'product', 'quantity', 'movement_type', 'date', 'description')
    list_filter = ('warehouse', 'product', 'movement_type', 'date')
    search_fields = ('warehouse__name', 'product__product_name', 'movement_type')


# TEMPORARY RESERVATION Admin ---------------------------------------------------------
@admin.register(TemporaryReservation)
class TemporaryReservationAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'reserved_quantity', 'created_at', 'expiry_date')
    list_filter = ('product', 'user', 'expiry_date')
    search_fields = ('product__name', 'user__username')
    actions = ['delete_expired_reservations']

    @admin.action(description="Delete expired reservations")
    def delete_expired_reservations(self, request, queryset):
        expired_reservations = queryset.filter(expiry_date__lt=timezone.now())
        count = expired_reservations.count()
        expired_reservations.delete()
        self.message_user(request, f"Successfully deleted {count} expired reservations.")
