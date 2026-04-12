# apps/bookstore_inventory/models/inbound.py

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.bookstore_inventory.constants import InboundPaymentStatus, InboundSourceType
from apps.bookstore_inventory.models.base import TimeStampedModel
from apps.bookstore_inventory.models.catalog import BookEdition
from apps.bookstore_inventory.models.warehouse import Warehouse


class InboundShipment(TimeStampedModel):
    # Warehouse inbound header
    shipment_number = models.CharField(max_length=40, unique=True, db_index=True)

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="inbound_shipments",
    )

    source_type = models.CharField(
        max_length=24,
        choices=InboundSourceType.choices,
        default=InboundSourceType.PURCHASE,
        db_index=True,
    )

    supplier_name = models.CharField(max_length=255, blank=True, db_index=True)
    supplier_contact = models.CharField(max_length=255, blank=True)
    supplier_phone = models.CharField(max_length=64, blank=True)
    invoice_reference = models.CharField(max_length=120, blank=True, db_index=True)

    received_at = models.DateTimeField(db_index=True)

    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    subtotal_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    payment_status = models.CharField(
        max_length=24,
        choices=InboundPaymentStatus.choices,
        default=InboundPaymentStatus.UNPAID,
        db_index=True,
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    currency = models.CharField(max_length=12, default="CAD")

    is_consignment = models.BooleanField(default=False, db_index=True)
    consignment_notes = models.TextField(blank=True)

    # Stock posting state
    stock_posted_at = models.DateTimeField(blank=True, null=True, db_index=True)
    stock_posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookstore_inbound_shipments_stock_posted",
    )

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookstore_inbound_shipments_created",
    )

    class Meta:
        ordering = ["-received_at", "-id"]
        verbose_name = "Inbound shipment"
        verbose_name_plural = "Inbound shipments"

    def __str__(self):
        return self.shipment_number

    def clean(self):
        # Validate source and payment logic
        if self.source_type == InboundSourceType.DONATION:
            if self.payment_status != InboundPaymentStatus.NOT_REQUIRED:
                raise ValidationError({
                    "payment_status": "Donation shipments should use 'Not required'."
                })

        if self.source_type == InboundSourceType.CONSIGNMENT and not self.is_consignment:
            raise ValidationError({
                "is_consignment": "Consignment source requires consignment flag."
            })

        if self.amount_paid < Decimal("0.00"):
            raise ValidationError({"amount_paid": "Amount paid cannot be negative."})

    @property
    def is_stock_posted(self):
        # Check posting state
        return self.stock_posted_at is not None

    def recalculate_totals(self, save=True):
        # Rebuild inbound financial summary
        subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        total = subtotal + self.shipping_cost + self.other_cost
        due = max(total - self.amount_paid, Decimal("0.00"))

        self.subtotal_cost = subtotal
        self.total_cost = total
        self.amount_due = due

        if self.source_type == InboundSourceType.DONATION:
            self.payment_status = InboundPaymentStatus.NOT_REQUIRED
        elif self.is_consignment:
            if self.amount_paid <= Decimal("0.00"):
                self.payment_status = InboundPaymentStatus.PAY_AFTER_SALE
            elif due > Decimal("0.00"):
                self.payment_status = InboundPaymentStatus.PARTIAL
            else:
                self.payment_status = InboundPaymentStatus.PAID
        else:
            if total == Decimal("0.00"):
                self.payment_status = InboundPaymentStatus.NOT_REQUIRED
            elif self.amount_paid == Decimal("0.00"):
                self.payment_status = InboundPaymentStatus.UNPAID
            elif due > Decimal("0.00"):
                self.payment_status = InboundPaymentStatus.PARTIAL
            else:
                self.payment_status = InboundPaymentStatus.PAID

        if save:
            self.save(
                update_fields=[
                    "subtotal_cost",
                    "total_cost",
                    "amount_due",
                    "payment_status",
                    "updated_at",
                ]
            )


class InboundShipmentItem(TimeStampedModel):
    # Shipment item line
    shipment = models.ForeignKey(
        InboundShipment,
        on_delete=models.CASCADE,
        related_name="items",
    )
    book_edition = models.ForeignKey(
        BookEdition,
        on_delete=models.PROTECT,
        related_name="inbound_items",
    )

    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Inbound shipment item"
        verbose_name_plural = "Inbound shipment items"

    def __str__(self):
        return f"{self.book_edition} x {self.quantity}"

    def clean(self):
        # Validate quantity
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})

    def save(self, *args, **kwargs):
        # Auto-calc line total
        self.line_total = (self.unit_cost or Decimal("0.00")) * self.quantity
        super().save(*args, **kwargs)


class InboundPayment(TimeStampedModel):
    # Payment made for inbound shipment
    shipment = models.ForeignKey(
        InboundShipment,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=12, default="CAD")
    payment_reference = models.CharField(max_length=120, blank=True, db_index=True)
    paid_at = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookstore_inbound_payments_recorded",
    )

    class Meta:
        ordering = ["-paid_at", "-id"]
        verbose_name = "Inbound payment"
        verbose_name_plural = "Inbound payments"

    def __str__(self):
        return f"{self.shipment.shipment_number} - {self.amount} {self.currency}"

    def clean(self):
        # Validate amount
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "Amount must be greater than zero."})