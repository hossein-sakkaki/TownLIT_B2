# apps/bookstore_inventory/models/inventory.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from apps.bookstore_inventory.constants import (
    STOCK_IN_TYPES, STOCK_OUT_TYPES, AdjustmentReason, DocumentStatus,
    InventoryCondition, ReservationStatus, ReturnDirection, StockCountStatus,
    StockMovementType, TransferStatus,
)
from apps.bookstore_inventory.models.base import TimeStampedModel
from apps.bookstore_inventory.models.catalog import BookEdition
from apps.bookstore_inventory.models.inbound import InboundShipment, InboundShipmentItem
from apps.bookstore_inventory.models.orders import BookOrder, BookOrderItem
from apps.bookstore_inventory.models.organizations import OrganizationRecord
from apps.bookstore_inventory.models.warehouse import Warehouse, WarehouseLocation


class InventoryBalance(TimeStampedModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="balances")
    on_hand_quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)
    unavailable_quantity = models.IntegerField(
        default=0,
        help_text="Damaged, display, quarantined, or unsellable stock.",
    )

    class Meta:
        ordering = ("warehouse__name", "book_edition__book__title")
        constraints = [
            models.UniqueConstraint(
                fields=("warehouse", "book_edition"),
                name="bookstore_unique_inventory_balance",
            ),
            models.CheckConstraint(
                check=Q(reserved_quantity__gte=0),
                name="bookstore_reserved_quantity_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(unavailable_quantity__gte=0),
                name="bookstore_unavailable_quantity_nonnegative",
            ),
        ]
        verbose_name = "Inventory balance"
        verbose_name_plural = "Inventory balances"

    def __str__(self):
        return f"{self.warehouse} - {self.book_edition}"

    @property
    def available_quantity(self):
        return self.on_hand_quantity - self.reserved_quantity - self.unavailable_quantity


class InventoryLot(TimeStampedModel):
    lot_number = models.CharField(max_length=80, unique=True, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="inventory_lots")
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_lots",
    )
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="inventory_lots")
    source_item = models.OneToOneField(
        InboundShipmentItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_lot",
    )
    condition = models.CharField(
        max_length=24, choices=InventoryCondition.choices,
        default=InventoryCondition.NEW, db_index=True,
    )
    received_at = models.DateTimeField(db_index=True)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=12, default="CAD")
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-received_at", "-id")
        verbose_name = "Inventory lot"
        verbose_name_plural = "Inventory lots"

    def __str__(self):
        return f"{self.lot_number} — {self.book_edition}"

    def clean(self):
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            raise ValidationError({"location": "Lot location must belong to its warehouse."})

    @property
    def on_hand_quantity(self):
        return StockMovement.calculate_on_hand(
            self.warehouse_id, self.book_edition_id, lot_id=self.pk,
        )


class StockMovement(TimeStampedModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements")
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movements",
    )
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="movements")
    lot = models.ForeignKey(
        InventoryLot, on_delete=models.PROTECT, null=True, blank=True,
        related_name="movements",
    )
    inbound_shipment = models.ForeignKey(
        InboundShipment, on_delete=models.PROTECT, null=True, blank=True,
        related_name="stock_movements",
    )
    movement_type = models.CharField(max_length=32, choices=StockMovementType.choices, db_index=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reference_type = models.CharField(max_length=80, blank=True, db_index=True)
    reference_id = models.CharField(max_length=80, blank=True, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bookstore_stock_movements",
    )
    performed_at = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-performed_at", "-id")
        indexes = [
            models.Index(fields=("warehouse", "book_edition")),
            models.Index(fields=("movement_type", "performed_at")),
            models.Index(fields=("reference_type", "reference_id")),
        ]
        verbose_name = "Stock movement"
        verbose_name_plural = "Stock movements"

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.book_edition} ({self.quantity})"

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors["quantity"] = "Quantity must be greater than zero."
        if self.unit_price < 0:
            errors["unit_price"] = "Unit price cannot be negative."
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            errors["location"] = "Location must belong to the selected warehouse."
        if self.lot_id and (
            self.lot.warehouse_id != self.warehouse_id
            or self.lot.book_edition_id != self.book_edition_id
        ):
            errors["lot"] = "Lot must match the selected warehouse and edition."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.total_amount and self.unit_price and self.quantity:
            self.total_amount = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    @property
    def signed_quantity(self):
        if self.movement_type in STOCK_IN_TYPES:
            return self.quantity
        if self.movement_type in STOCK_OUT_TYPES:
            return -self.quantity
        return 0

    @classmethod
    def calculate_on_hand(cls, warehouse_id, book_edition_id, lot_id=None):
        queryset = cls.objects.filter(warehouse_id=warehouse_id, book_edition_id=book_edition_id)
        if lot_id is not None:
            queryset = queryset.filter(lot_id=lot_id)
        incoming = queryset.filter(movement_type__in=STOCK_IN_TYPES).aggregate(
            total=Coalesce(Sum("quantity"), 0)
        )["total"]
        outgoing = queryset.filter(movement_type__in=STOCK_OUT_TYPES).aggregate(
            total=Coalesce(Sum("quantity"), 0)
        )["total"]
        return incoming - outgoing


class StockReservation(TimeStampedModel):
    order_item = models.ForeignKey(BookOrderItem, on_delete=models.PROTECT, related_name="reservations")
    active_order_item = models.OneToOneField(
        BookOrderItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="active_stock_reservation", editable=False,
        help_text="MySQL-safe uniqueness key; populated only while active.",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="reservations")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="reservations")
    quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=ReservationStatus.choices,
        default=ReservationStatus.ACTIVE, db_index=True,
    )
    reserved_at = models.DateTimeField(db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookstore_stock_reserved",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-reserved_at", "-id")
        verbose_name = "Stock reservation"
        verbose_name_plural = "Stock reservations"

    def __str__(self):
        return f"{self.order_item} — {self.quantity} reserved"

    def clean(self):
        if self.status == ReservationStatus.ACTIVE:
            if self.active_order_item_id not in {None, self.order_item_id}:
                raise ValidationError({
                    "active_order_item": "Active key must match the order item."
                })
        elif self.active_order_item_id:
            raise ValidationError({
                "active_order_item": "Closed reservations cannot retain an active key."
            })

    def save(self, *args, **kwargs):
        self.active_order_item_id = (
            self.order_item_id if self.status == ReservationStatus.ACTIVE else None
        )
        super().save(*args, **kwargs)


class StockTransfer(TimeStampedModel):
    transfer_number = models.CharField(
        max_length=40, unique=True, db_index=True, blank=True,
        help_text="Generated automatically when left blank.",
    )
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="outgoing_transfers")
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="incoming_transfers")
    status = models.CharField(
        max_length=20, choices=TransferStatus.choices,
        default=TransferStatus.DRAFT, db_index=True,
    )
    dispatched_at = models.DateTimeField(null=True, blank=True, db_index=True)
    received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="bookstore_transfers_created")
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookstore_transfers_dispatched")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookstore_transfers_received")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        permissions = (
            ("dispatch_stocktransfer", "Can dispatch stock transfers"),
            ("receive_stocktransfer", "Can receive stock transfers"),
        )
        verbose_name = "Stock transfer"
        verbose_name_plural = "Stock transfers"

    def __str__(self):
        return self.transfer_number

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            from apps.bookstore_inventory.services.numbering import generate_transfer_number

            self.transfer_number = generate_transfer_number()
        super().save(*args, **kwargs)

    def clean(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValidationError({"to_warehouse": "Source and destination warehouses must differ."})


class StockTransferItem(TimeStampedModel):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="items")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="transfer_items")
    source_location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="transfer_items_out")
    destination_location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="transfer_items_in")
    source_lot = models.ForeignKey(InventoryLot, on_delete=models.PROTECT, null=True, blank=True, related_name="transfer_items")
    quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Stock transfer item"
        verbose_name_plural = "Stock transfer items"

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors["quantity"] = "Quantity must be greater than zero."
        if self.received_quantity > self.quantity:
            errors["received_quantity"] = "Received quantity cannot exceed dispatched quantity."
        if self.source_location_id and self.source_location.warehouse_id != self.transfer.from_warehouse_id:
            errors["source_location"] = "Source location must belong to the source warehouse."
        if self.destination_location_id and self.destination_location.warehouse_id != self.transfer.to_warehouse_id:
            errors["destination_location"] = "Destination location must belong to the destination warehouse."
        if errors:
            raise ValidationError(errors)


class StockCount(TimeStampedModel):
    count_number = models.CharField(
        max_length=40, unique=True, db_index=True, blank=True,
        help_text="Generated automatically when left blank.",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_counts")
    location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_counts")
    status = models.CharField(max_length=20, choices=StockCountStatus.choices, default=StockCountStatus.DRAFT, db_index=True)
    counted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="bookstore_counts_created")
    counted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookstore_counts_performed")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookstore_counts_posted")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        permissions = (
            ("snapshot_stockcount", "Can capture expected stock-count quantities"),
            ("post_stockcount", "Can post stock-count variances"),
        )
        verbose_name = "Stock count"
        verbose_name_plural = "Stock counts"

    def __str__(self):
        return self.count_number

    def save(self, *args, **kwargs):
        if not self.count_number:
            from apps.bookstore_inventory.services.numbering import generate_stock_count_number

            self.count_number = generate_stock_count_number()
        super().save(*args, **kwargs)


class StockCountItem(TimeStampedModel):
    stock_count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="items")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="stock_count_items")
    lot = models.ForeignKey(InventoryLot, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_count_items")
    expected_quantity = models.IntegerField(default=0)
    counted_quantity = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=32, choices=AdjustmentReason.choices, default=AdjustmentReason.COUNT_VARIANCE)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("book_edition__book__title", "id")
        verbose_name = "Stock count item"
        verbose_name_plural = "Stock count items"

    @property
    def variance(self):
        return self.counted_quantity - self.expected_quantity


class StockAdjustment(TimeStampedModel):
    adjustment_number = models.CharField(
        max_length=40, unique=True, db_index=True, blank=True,
        help_text="Generated automatically when left blank.",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="adjustments")
    status = models.CharField(max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT, db_index=True)
    reason = models.CharField(max_length=32, choices=AdjustmentReason.choices)
    posted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="bookstore_adjustments_created")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookstore_adjustments_posted")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        permissions = (("post_stockadjustment", "Can post stock adjustments"),)
        verbose_name = "Stock adjustment"
        verbose_name_plural = "Stock adjustments"

    def __str__(self):
        return self.adjustment_number

    def save(self, *args, **kwargs):
        if not self.adjustment_number:
            from apps.bookstore_inventory.services.numbering import generate_adjustment_number

            self.adjustment_number = generate_adjustment_number()
        super().save(*args, **kwargs)


class StockAdjustmentItem(TimeStampedModel):
    adjustment = models.ForeignKey(StockAdjustment, on_delete=models.CASCADE, related_name="items")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="adjustment_items")
    location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustment_items")
    lot = models.ForeignKey(InventoryLot, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustment_items")
    quantity_delta = models.IntegerField(help_text="Positive to add stock; negative to remove stock.")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Stock adjustment item"
        verbose_name_plural = "Stock adjustment items"

    def clean(self):
        if self.quantity_delta == 0:
            raise ValidationError({"quantity_delta": "Adjustment cannot be zero."})


class StockReturn(TimeStampedModel):
    return_number = models.CharField(
        max_length=40, unique=True, db_index=True, blank=True,
        help_text="Generated automatically when left blank.",
    )
    direction = models.CharField(max_length=32, choices=ReturnDirection.choices, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="returns")
    order = models.ForeignKey(BookOrder, on_delete=models.PROTECT, null=True, blank=True, related_name="returns")
    supplier = models.ForeignKey(OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_returns")
    status = models.CharField(max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="bookstore_returns_created")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookstore_returns_posted")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        permissions = (("post_stockreturn", "Can post stock returns"),)
        verbose_name = "Stock return"
        verbose_name_plural = "Stock returns"

    def __str__(self):
        return self.return_number

    def save(self, *args, **kwargs):
        if not self.return_number:
            from apps.bookstore_inventory.services.numbering import generate_return_number

            self.return_number = generate_return_number()
        super().save(*args, **kwargs)

    def clean(self):
        if self.direction == ReturnDirection.CUSTOMER_TO_STOCK and not self.order_id:
            raise ValidationError({"order": "Customer returns must reference an order."})
        if self.direction == ReturnDirection.STOCK_TO_SUPPLIER and not self.supplier_id:
            raise ValidationError({"supplier": "Supplier returns must reference a supplier."})


class StockReturnItem(TimeStampedModel):
    stock_return = models.ForeignKey(StockReturn, on_delete=models.CASCADE, related_name="items")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="return_items")
    location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="return_items")
    lot = models.ForeignKey(InventoryLot, on_delete=models.PROTECT, null=True, blank=True, related_name="return_items")
    condition = models.CharField(max_length=24, choices=InventoryCondition.choices, default=InventoryCondition.GOOD)
    quantity = models.PositiveIntegerField()
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Stock return item"
        verbose_name_plural = "Stock return items"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
