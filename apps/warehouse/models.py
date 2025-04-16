from django.db import models
from django.utils import timezone
from django.utils import timezone
from datetime import timedelta
from apps.products.models import Product
from apps.store.models import Store
from apps.accounts.models import Address
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# WAREHOUSE Model ------------------------------------------------------------------
class Warehouse(models.Model):
    name = models.CharField(max_length=100, verbose_name='Warehouse Name')
    location = models.CharField(max_length=255, verbose_name='Location')
    warehouse_address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, related_name='warehouse_address', verbose_name='Warehouse Address')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='warehouses', verbose_name='Store')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')
    is_temporarily_closed = models.BooleanField(default=False, verbose_name='Is Temporarily Closed')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = 'Warehouse'
        verbose_name_plural = 'Warehouses'

    def __str__(self):
        return f"{self.name} - {self.store.name}"


# WAREHOUSE INVENTORY Model ---------------------------------------------------------
class WarehouseInventory(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory', verbose_name='Warehouse')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='warehouse_inventory', verbose_name='Product')
    quantity = models.PositiveIntegerField(default=0, verbose_name='Quantity')
    reserved_quantity = models.PositiveIntegerField(default=0, verbose_name="Reserved Quantity")  # Added field
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Last Updated')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = 'Warehouse Inventory'
        verbose_name_plural = 'Warehouse Inventories'
        unique_together = ['warehouse', 'product']

    def __str__(self):
        return f"{self.product.product_name} - {self.warehouse.name} - Quantity: {self.quantity}"


# STOCK MOVEMENT Model --------------------------------------------------------------
class StockMovement(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_movements', verbose_name='Warehouse')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements', verbose_name='Product')
    quantity = models.IntegerField(verbose_name='Quantity')  # Can be positive (inflow) or negative (outflow)
    movement_type = models.CharField(max_length=50, choices=[('inflow', 'Inflow'), ('outflow', 'Outflow')], verbose_name='Movement Type')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    date = models.DateTimeField(default=timezone.now, verbose_name='Movement Date')

    class Meta:
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        return f"{self.movement_type} - {self.product.product_name} - {self.quantity} units - {self.warehouse.name}"
    

# TEMPORARY RESERVATION Model --------------------------------------------------------------
class TemporaryReservation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='temporary_reservations', verbose_name="Product")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='temporary_reservations', verbose_name="User")
    reserved_quantity = models.PositiveIntegerField(verbose_name="Reserved Quantity")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created At")
    expiry_date = models.DateTimeField(verbose_name="Expiry Date")

    def save(self, *args, **kwargs):
        if not self.expiry_date:
            self.expiry_date = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Temporary Reservation"
        verbose_name_plural = "Temporary Reservations"

    def __str__(self):
        return f"Reservation for {self.product.name} by {self.user.username}"
