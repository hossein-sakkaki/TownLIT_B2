# apps/bookstore_inventory/models/inbound.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    InboundPaymentScheduleStatus, InboundPaymentStatus, InboundSourceType,
    InventoryCondition,
)
from apps.bookstore_inventory.models.base import TimeStampedModel
from apps.bookstore_inventory.models.catalog import BookEdition
from apps.bookstore_inventory.models.organizations import OrganizationRecord
from apps.bookstore_inventory.models.warehouse import Warehouse, WarehouseLocation


class InboundShipment(TimeStampedModel):
    shipment_number = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Generated automatically when left blank.",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="inbound_shipments"
    )
    source_type = models.CharField(
        max_length=24, choices=InboundSourceType.choices,
        default=InboundSourceType.PURCHASE, db_index=True,
    )
    supplier = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="supplied_shipments",
    )
    donor = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="donated_shipments",
        help_text="Who donated the goods or funded this acquisition, when applicable.",
    )
    supplier_name = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="Historical supplier-name snapshot.",
    )
    donor_name = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="Historical donor-name snapshot.",
    )
    supplier_contact = models.CharField(max_length=255, blank=True)
    supplier_phone = models.CharField(max_length=64, blank=True)
    invoice_reference = models.CharField(max_length=120, blank=True, db_index=True)
    received_at = models.DateTimeField(db_index=True)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    subtotal_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_status = models.CharField(
        max_length=24, choices=InboundPaymentStatus.choices,
        default=InboundPaymentStatus.UNPAID, db_index=True,
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=12, default="CAD")
    is_consignment = models.BooleanField(default=False, db_index=True)
    consignment_notes = models.TextField(blank=True)
    stock_posted_at = models.DateTimeField(blank=True, null=True, db_index=True)
    stock_posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookstore_inbound_shipments_stock_posted",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookstore_inbound_shipments_created",
    )

    class Meta:
        ordering = ("-received_at", "-id")
        permissions = (("post_inboundshipment", "Can post inbound shipments to stock"),)
        verbose_name = "Inbound shipment"
        verbose_name_plural = "Inbound shipments"

    def __str__(self):
        return self.shipment_number

    def clean(self):
        errors = {}
        if self.source_type == InboundSourceType.DONATION:
            self.payment_status = InboundPaymentStatus.NOT_REQUIRED
        if self.source_type == InboundSourceType.CONSIGNMENT and not self.is_consignment:
            errors["is_consignment"] = "Consignment source requires the consignment flag."
        if self.shipping_cost < 0:
            errors["shipping_cost"] = "Shipping cost cannot be negative."
        if self.other_cost < 0:
            errors["other_cost"] = "Other cost cannot be negative."
        if self.amount_paid < 0:
            errors["amount_paid"] = "Amount paid cannot be negative."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            from apps.bookstore_inventory.services.numbering import generate_shipment_number

            self.shipment_number = generate_shipment_number()
        if self.source_type == InboundSourceType.DONATION:
            self.payment_status = InboundPaymentStatus.NOT_REQUIRED
        if self.supplier_id and not self.supplier_name:
            self.supplier_name = str(self.supplier)
        if self.donor_id and not self.donor_name:
            self.donor_name = str(self.donor)
        super().save(*args, **kwargs)

    @property
    def is_stock_posted(self):
        return self.stock_posted_at is not None

    def recalculate_totals(self, save=True):
        subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        total = subtotal + self.shipping_cost + self.other_cost
        due = max(total - self.amount_paid, Decimal("0.00"))
        if self.source_type == InboundSourceType.DONATION:
            # Goods are not payable to the donor. Any carrier/handling cash
            # expense is recorded separately in the cash ledger.
            due = Decimal("0.00")
        self.subtotal_cost, self.total_cost, self.amount_due = subtotal, total, due
        if self.source_type == InboundSourceType.DONATION:
            self.payment_status = InboundPaymentStatus.NOT_REQUIRED
        elif self.is_consignment and self.amount_paid <= 0:
            self.payment_status = InboundPaymentStatus.PAY_AFTER_SALE
        elif total == 0:
            self.payment_status = InboundPaymentStatus.NOT_REQUIRED
        elif self.amount_paid == 0:
            self.payment_status = InboundPaymentStatus.UNPAID
        elif due > 0:
            self.payment_status = InboundPaymentStatus.PARTIAL
        else:
            self.payment_status = InboundPaymentStatus.PAID
        if save:
            self.save(update_fields=(
                "subtotal_cost", "total_cost", "amount_paid", "amount_due",
                "payment_status", "updated_at",
            ))

    @property
    def scheduled_remaining_amount(self):
        return sum(
            (schedule.remaining_amount for schedule in self.payment_schedules.all()),
            Decimal("0.00"),
        )

    @property
    def overdue_amount(self):
        return sum(
            (
                schedule.remaining_amount
                for schedule in self.payment_schedules.all()
                if schedule.is_overdue
            ),
            Decimal("0.00"),
        )

    @property
    def unplanned_due_amount(self):
        return max(
            self.amount_due - self.scheduled_remaining_amount,
            Decimal("0.00"),
        )


class InboundShipmentItem(TimeStampedModel):
    shipment = models.ForeignKey(InboundShipment, on_delete=models.CASCADE, related_name="items")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="inbound_items")
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inbound_items",
    )
    lot_number = models.CharField(
        max_length=80, blank=True, db_index=True,
        help_text="Optional supplier batch/lot number; one will be generated when blank.",
    )
    condition = models.CharField(
        max_length=24, choices=InventoryCondition.choices,
        default=InventoryCondition.NEW, db_index=True,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Inbound shipment item"
        verbose_name_plural = "Inbound shipment items"

    def __str__(self):
        return f"{self.book_edition} x {self.quantity}"

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors["quantity"] = "Quantity must be greater than zero."
        if self.unit_cost < 0:
            errors["unit_cost"] = "Unit cost cannot be negative."
        if self.location_id and self.shipment_id and self.location.warehouse_id != self.shipment.warehouse_id:
            errors["location"] = "Location must belong to the shipment warehouse."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.line_total = (self.unit_cost or Decimal("0.00")) * self.quantity
        super().save(*args, **kwargs)


class InboundPaymentSchedule(TimeStampedModel):
    """One supplier-payable installment for an inbound shipment."""

    shipment = models.ForeignKey(
        InboundShipment,
        on_delete=models.CASCADE,
        related_name="payment_schedules",
    )
    due_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=12, default="CAD")
    status = models.CharField(
        max_length=20,
        choices=InboundPaymentScheduleStatus.choices,
        default=InboundPaymentScheduleStatus.SCHEDULED,
        db_index=True,
        editable=False,
    )
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookstore_inbound_schedules_created",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("due_date", "id")
        indexes = [
            models.Index(fields=("shipment", "due_date")),
            models.Index(fields=("status", "due_date")),
        ]
        verbose_name = "Inbound payment schedule"
        verbose_name_plural = "Inbound payment schedules"

    def __str__(self):
        return (
            f"{self.shipment.shipment_number} — {self.due_date} — "
            f"{self.amount} {self.currency}"
        )

    @property
    def paid_amount(self):
        return sum(
            (payment.amount for payment in self.payments.all()),
            Decimal("0.00"),
        )

    @property
    def remaining_amount(self):
        return max(self.amount - self.paid_amount, Decimal("0.00"))

    @property
    def is_overdue(self):
        return bool(
            self.remaining_amount > Decimal("0.00")
            and self.due_date < timezone.localdate()
        )

    def clean(self):
        errors = {}
        if self.amount <= Decimal("0.00"):
            errors["amount"] = "Scheduled amount must be greater than zero."
        if self.shipment_id:
            if self.currency != self.shipment.currency:
                errors["currency"] = "Schedule currency must match the shipment currency."
            if self.shipment.source_type == InboundSourceType.DONATION:
                errors["shipment"] = "Donation shipments cannot have supplier payment schedules."
            paid = self.paid_amount if self.pk else Decimal("0.00")
            if paid > self.amount:
                errors["amount"] = "Scheduled amount cannot be less than payments already assigned to it."
        if errors:
            raise ValidationError(errors)

    def refresh_status(self):
        paid = self.paid_amount
        if paid <= Decimal("0.00"):
            status = InboundPaymentScheduleStatus.SCHEDULED
        elif paid < self.amount:
            status = InboundPaymentScheduleStatus.PARTIAL
        else:
            status = InboundPaymentScheduleStatus.PAID
        if self.status != status:
            type(self).objects.filter(pk=self.pk).update(
                status=status,
                updated_at=timezone.now(),
            )
            self.status = status
        return status

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.refresh_status()


class InboundPayment(TimeStampedModel):
    shipment = models.ForeignKey(InboundShipment, on_delete=models.CASCADE, related_name="payments")
    schedule = models.ForeignKey(
        InboundPaymentSchedule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Optional installment that this payment settles.",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=12, default="CAD")
    settlement_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual cash amount paid; defaults to Amount.",
    )
    settlement_currency = models.CharField(
        max_length=12,
        blank=True,
        help_text="Actual cash currency; defaults to Currency.",
    )
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        null=True,
        blank=True,
        help_text=(
            "Shipment-currency units applied per one settlement-currency unit. "
            "Required only for cross-currency payments."
        ),
    )
    payment_reference = models.CharField(max_length=120, blank=True, db_index=True)
    paid_at = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookstore_inbound_payments_recorded",
    )

    class Meta:
        ordering = ("-paid_at", "-id")
        verbose_name = "Inbound payment"
        verbose_name_plural = "Inbound payments"

    def __str__(self):
        return f"{self.shipment.shipment_number} - {self.amount} {self.currency}"

    def clean(self):
        errors = {}
        if self.amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
        if self.shipment_id:
            if self.currency != self.shipment.currency:
                errors["currency"] = "Payment currency must match the shipment currency."
            if self.shipment.source_type == InboundSourceType.DONATION:
                errors["shipment"] = "Donation shipments cannot have supplier payments."
        if self.schedule_id:
            if self.schedule.shipment_id != self.shipment_id:
                errors["schedule"] = "Payment schedule must belong to this shipment."
            if self.schedule.currency != self.currency:
                errors["schedule"] = "Payment and schedule currencies must match."
            other_paid = sum(
                (
                    payment.amount
                    for payment in self.schedule.payments.exclude(pk=self.pk)
                ),
                Decimal("0.00"),
            )
            if other_paid + (self.amount or Decimal("0.00")) > self.schedule.amount:
                errors["amount"] = "Payment exceeds the remaining scheduled amount."
        settlement_amount = (
            self.settlement_amount
            if self.settlement_amount is not None
            else self.amount
        )
        settlement_currency = self.settlement_currency or self.currency
        if settlement_amount is not None and settlement_amount <= Decimal("0.00"):
            errors["settlement_amount"] = "Settlement amount must be greater than zero."
        if settlement_currency == self.currency:
            if (
                self.settlement_amount is not None
                and self.amount is not None
                and self.settlement_amount != self.amount
            ):
                errors["settlement_amount"] = (
                    "Same-currency settlement amount must equal the applied amount."
                )
            if self.exchange_rate not in {None, Decimal("1"), Decimal("1.0")}:
                errors["exchange_rate"] = "Same-currency payments do not need an exchange rate."
        else:
            if not self.exchange_rate or self.exchange_rate <= Decimal("0.00"):
                errors["exchange_rate"] = "Cross-currency payments require a positive exchange rate."
            elif settlement_amount is not None and self.amount is not None:
                applied = settlement_amount * self.exchange_rate
                if abs(applied - self.amount) > Decimal("0.02"):
                    errors["exchange_rate"] = (
                        "Settlement amount multiplied by the exchange rate must "
                        "match the applied shipment amount (within 0.02)."
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.settlement_currency:
            self.settlement_currency = self.currency
        if self.settlement_amount is None:
            self.settlement_amount = self.amount
        if self.settlement_currency == self.currency:
            self.exchange_rate = None
        super().save(*args, **kwargs)

    @property
    def cash_amount(self):
        return self.settlement_amount if self.settlement_amount is not None else self.amount

    @property
    def cash_currency(self):
        return self.settlement_currency or self.currency
