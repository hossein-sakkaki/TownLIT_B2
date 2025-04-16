from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory, DeliveryInformation, ReturnRequest, ShoppingCart, ShoppingCartItem




# ORDER ADMIN --------------------------------------------------------------------------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'status', 'order_date', 'store', 'is_help_requested']
    list_filter = ['status', 'order_date']
    search_fields = ['id', 'customer__name__username']
    ordering = ['-order_date']
    readonly_fields = ['order_date']

    fieldsets = (
        ('Order Details', {'fields': ('customer', 'store', 'status', 'billing_address', 'shipping_address', 'total_price', 'notes')}),
        ('Help Details', {'fields': ('is_help_requested', 'help_message')}),
        ('Timestamps', {'fields': ('order_date',)}),
    )

# ORDER ITEM ADMIN ---------------------------------------------------------------------------
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price_at_purchase']
    list_filter = ['order']
    search_fields = ['order__id', 'product__name']
    ordering = ['-order__order_date']

# ORDER STATUS HISTORY ADMIN -----------------------------------------------------------------
@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'change_date']
    list_filter = ['status', 'change_date']
    search_fields = ['order__id']
    ordering = ['-change_date']

# DELIVERY INFORMATION ADMIN -----------------------------------------------------------------
@admin.register(DeliveryInformation)
class DeliveryInformationAdmin(admin.ModelAdmin):
    list_display = ['order', 'carrier', 'tracking_number', 'status', 'estimated_delivery_date']
    list_filter = ['carrier', 'status']
    search_fields = ['order__id', 'tracking_number']
    ordering = ['-estimated_delivery_date']

    fieldsets = (
        ('Delivery Details', {'fields': ('order', 'carrier', 'tracking_number', 'tracking_url', 'status', 'estimated_delivery_date', 'actual_delivery_date', 'carrier_contact_number')}),
    )

# RETURN REQUEST ADMIN -----------------------------------------------------------------------
@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ['order_item', 'reason', 'status', 'request_date']
    list_filter = ['status', 'request_date']
    search_fields = ['order_item__order__id', 'reason']
    ordering = ['-request_date']

    fieldsets = (
        ('Return Request Details', {'fields': ('order_item', 'reason', 'status', 'request_date', 'handled_by')}),
    )

# SHOPPING CART ADMIN ------------------------------------------------------------------------
@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ['customer', 'created_at', 'updated_at']
    search_fields = ['customer__name__username']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

# SHOPPING CART ITEM ADMIN -------------------------------------------------------------------
@admin.register(ShoppingCartItem)
class ShoppingCartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'quantity']
    list_filter = ['cart']
    search_fields = ['cart__customer__name__username', 'product__name']
    ordering = ['-cart__created_at']
