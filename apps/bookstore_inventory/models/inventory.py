# apps/bookstore_inventory/models/inventory.py

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.conf import settings

from apps.bookstore_inventory.constants import STOCK_IN_TYPES, STOCK_OUT_TYPES, StockMovementType
from apps.bookstore_inventory.models.base import TimeStampedModel
from apps.bookstore_inventory.models.catalog import BookEdition
from apps.bookstore_inventory.models.inbound import InboundShipment
from apps.bookstore_inventory.models.warehouse import Warehouse


class InventoryBalance(TimeStampedModel):
    # Fast stock snapshot
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="balances",
    )
    book_edition = models.ForeignKey(
        BookEdition,
        on_delete=models.CASCADE,
        related_name="balances",
    )

    on_hand_quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = ("warehouse", "book_edition")
        ordering = ["warehouse__name", "book_edition__book__title"]
        verbose_name = "Inventory balance"
        verbose_name_plural = "Inventory balances"

    def __str__(self):
        return f"{self.warehouse} - {self.book_edition}"

    @property
    def available_quantity(self):
        return self.on_hand_quantity - self.reserved_quantity


class StockMovement(TimeStampedModel):
    # Stock movement history
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    book_edition = models.ForeignKey(
        BookEdition,
        on_delete=models.CASCADE,
        related_name="movements",
    )

    inbound_shipment = models.ForeignKey(
        InboundShipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    movement_type = models.CharField(
        max_length=32,
        choices=StockMovementType.choices,
        db_index=True,
    )
    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    reference_type = models.CharField(max_length=80, blank=True, db_index=True)
    reference_id = models.CharField(max_length=80, blank=True, db_index=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bookstore_stock_movements",
    )
    performed_at = models.DateTimeField(db_index=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-performed_at", "-id"]
        verbose_name = "Stock movement"
        verbose_name_plural = "Stock movements"
        indexes = [
            models.Index(fields=["warehouse", "book_edition"]),
            models.Index(fields=["movement_type", "performed_at"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.book_edition} ({self.quantity})"

    def clean(self):
        # Validate movement
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})

        if self.total_amount == Decimal("0.00") and self.unit_price and self.quantity:
            self.total_amount = self.unit_price * self.quantity

    @property
    def signed_quantity(self):
        # Return signed quantity
        if self.movement_type in STOCK_IN_TYPES:
            return self.quantity
        if self.movement_type in STOCK_OUT_TYPES:
            return -self.quantity
        return 0

    @classmethod
    def calculate_on_hand(cls, warehouse_id, book_edition_id):
        # Rebuild stock from movement history
        incoming = cls.objects.filter(
            warehouse_id=warehouse_id,
            book_edition_id=book_edition_id,
            movement_type__in=STOCK_IN_TYPES,
        ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"]

        outgoing = cls.objects.filter(
            warehouse_id=warehouse_id,
            book_edition_id=book_edition_id,
            movement_type__in=STOCK_OUT_TYPES,
        ).aggregate(total=Coalesce(Sum("quantity"), 0))["total"]

        return incoming - outgoing