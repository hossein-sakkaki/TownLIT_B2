# apps/bookstore_inventory/models/warehouse.py

from django.db import models

from apps.bookstore_inventory.models.base import TimeStampedModel


class Warehouse(TimeStampedModel):
    # Physical warehouse
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=32, unique=True, db_index=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True, db_index=True)
    province_state = models.CharField(max_length=120, blank=True, db_index=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=120, blank=True, default="Canada")
    contact_name = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        # Build readable address
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.province_state,
            self.postal_code,
            self.country,
        ]
        return ", ".join(part for part in parts if part)