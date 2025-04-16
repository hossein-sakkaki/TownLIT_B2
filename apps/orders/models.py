from django.db import models
from django.utils import timezone
from apps.products.models import Product
from apps.store.models import Store
from apps.accounts.models import CustomUser
from apps.profiles.models import Customer, Address

from apps.config.orders_constants import (
                                ORDER_STATUS_CHOICES,
                                DELIVERY_ORDER_STATUS_CHOICES, DELIVERY_IN_PAYMENT,
                                RETURN_ORDER_STATUS_CHOICES, PENDING
                            )



# ORDER Model ---------------------------------------------------------------
class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders', verbose_name='Customer')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders', verbose_name='Store')
    order_date = models.DateTimeField(default=timezone.now, verbose_name='Order Date')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default=PENDING, verbose_name='Order Status')
    billing_address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='order_billing_addresses', verbose_name='Billing Address')
    shipping_address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='order_shipping_addresses', verbose_name='Shipping Address')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Total Price')
    notes = models.TextField(null=True, blank=True, verbose_name='Order Notes')
    is_help_requested = models.BooleanField(default=False, verbose_name='Help Requested')
    help_message = models.TextField(null=True, blank=True, verbose_name='Help Message')

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-order_date']

    def __str__(self):
        return f"Order #{self.id} by {self.customer}"

# ORDER ITEM Model ------------------------------------------------------------
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Order')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items', verbose_name='Product')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Quantity')
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Price at Purchase')

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.quantity} x {self.product} (Order #{self.order.id})"

# ORDER STATUS HISTORY Model ------------------------------------------------------------
class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history', verbose_name='Order')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, verbose_name='Order Status')
    change_date = models.DateTimeField(default=timezone.now, verbose_name='Change Date')
    changed_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='changed_orders', verbose_name='Changed By')

    class Meta:
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-change_date']

    def __str__(self):
        return f"Order #{self.order.id} changed to {self.get_status_display()} on {self.change_date}"

# DELIVERY INFORMATION Model ------------------------------------------------------------
class DeliveryInformation(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_info', verbose_name='Order')
    carrier = models.CharField(max_length=100, verbose_name='Delivery Carrier')
    tracking_number = models.CharField(max_length=100, null=True, blank=True, verbose_name='Tracking Number')
    estimated_delivery_date = models.DateTimeField(null=True, blank=True, verbose_name='Estimated Delivery Date')
    actual_delivery_date = models.DateTimeField(null=True, blank=True, verbose_name='Actual Delivery Date')
    carrier_contact_number = models.CharField(max_length=20, null=True, blank=True, verbose_name='Carrier Contact Number')
    status = models.CharField(max_length=20, choices=DELIVERY_ORDER_STATUS_CHOICES, default=DELIVERY_IN_PAYMENT, verbose_name='Delivery Status')
    tracking_url = models.URLField(max_length=500, null=True, blank=True, verbose_name='Tracking URL')

    class Meta:
        verbose_name = 'Delivery Information'
        verbose_name_plural = 'Delivery Information'

    def __str__(self):
        return f"Delivery Info for Order #{self.order.id}"

# RETURN REQUEST Model ------------------------------------------------------------
class ReturnRequest(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_requests', verbose_name='Order Item')
    request_date = models.DateTimeField(default=timezone.now, verbose_name='Request Date')
    reason = models.TextField(verbose_name='Reason for Return')
    status = models.CharField(max_length=20, choices=RETURN_ORDER_STATUS_CHOICES, default=PENDING, verbose_name='Request Status')
    handled_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, null=True, blank=True, related_name='handled_returns', verbose_name='Handled By')

    class Meta:
        verbose_name = 'Return Request'
        verbose_name_plural = 'Return Requests'
        ordering = ['-request_date']

    def __str__(self):
        return f"Return Request for OrderItem #{self.order_item.id} ({self.get_status_display()})"

# SHOPPING CART Model ------------------------------------------------------------
class ShoppingCart(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='shopping_cart', verbose_name='Customer')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        verbose_name = 'Shopping Cart'
        verbose_name_plural = 'Shopping Carts'

    def __str__(self):
        return f"Shopping Cart for {self.customer.name.username}"

# SHOPPING CART ITEM Model ------------------------------------------------------------
class ShoppingCartItem(models.Model):
    cart = models.ForeignKey(ShoppingCart, on_delete=models.CASCADE, related_name='items', verbose_name='Shopping Cart')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='shopping_cart_items', verbose_name='Product')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Quantity')

    class Meta:
        verbose_name = 'Shopping Cart Item'
        verbose_name_plural = 'Shopping Cart Items'

    def __str__(self):
        return f"{self.quantity} x {self.product} in Cart for {self.cart.customer.name.username}"
