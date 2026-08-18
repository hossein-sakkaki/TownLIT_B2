# apps/bookstore_inventory/models/orders.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.bookstore_inventory.constants import (
    DeliveryMethod, OrderPurpose, OrderStatus, OrderType, PaymentMethod,
    PaymentStatus, PricingMode, RecipientType,
)
from apps.bookstore_inventory.models.base import TimeStampedModel
from apps.bookstore_inventory.models.catalog import BookEdition
from apps.bookstore_inventory.models.organizations import OrganizationRecord
from apps.bookstore_inventory.models.warehouse import Warehouse, WarehouseLocation


class BookOrder(TimeStampedModel):
    order_number = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Generated automatically when left blank.",
    )
    order_type = models.CharField(
        max_length=32, choices=OrderType.choices, default=OrderType.SALE, db_index=True,
    )
    status = models.CharField(
        max_length=24, choices=OrderStatus.choices, default=OrderStatus.DRAFT, db_index=True,
    )
    payment_status = models.CharField(
        max_length=24, choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID, db_index=True,
    )
    recipient_type = models.CharField(
        max_length=24, choices=RecipientType.choices,
        default=RecipientType.PERSON, db_index=True,
    )
    recipient_organization = models.ForeignKey(
        OrganizationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="book_orders_received",
    )
    recipient_first_name = models.CharField(max_length=120, blank=True)
    recipient_last_name = models.CharField(max_length=120, blank=True)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=64, blank=True)
    organization_name = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text="Historical recipient-name snapshot.",
    )
    organization_contact_person = models.CharField(max_length=255, blank=True)
    organization_email = models.EmailField(blank=True)
    organization_phone = models.CharField(max_length=64, blank=True)
    delivery_method = models.CharField(
        max_length=24, choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP, db_index=True,
    )
    purpose = models.CharField(
        max_length=32, choices=OrderPurpose.choices,
        default=OrderPurpose.PERSONAL_SALE, db_index=True,
    )
    destination_name = models.CharField(max_length=255, blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True, db_index=True)
    province_state = models.CharField(max_length=120, blank=True, db_index=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=120, blank=True, default="Canada")
    currency = models.CharField(max_length=12, default="CAD")
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    donation_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    fulfilled_at = models.DateTimeField(blank=True, null=True, db_index=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bookstore_orders_fulfilled",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bookstore_orders_created",
    )

    class Meta:
        ordering = ("-created_at", "-id")
        permissions = (
            ("reserve_bookorder", "Can reserve stock for book orders"),
            ("fulfill_bookorder", "Can fulfil book orders and deduct stock"),
        )
        verbose_name = "Book order"
        verbose_name_plural = "Book orders"

    def __str__(self):
        return self.order_number

    @property
    def is_fulfilled(self):
        return self.fulfilled_at is not None

    @property
    def recipient_display(self):
        if self.recipient_type == RecipientType.ORGANIZATION:
            return self.organization_name or str(self.recipient_organization or "Organization")
        full_name = f"{self.recipient_first_name} {self.recipient_last_name}".strip()
        return full_name or self.recipient_email or self.recipient_phone or "Person"

    def clean(self):
        errors = {}
        if self.recipient_type == RecipientType.ORGANIZATION and not (
            self.recipient_organization_id or self.organization_name.strip()
        ):
            errors["recipient_organization"] = "Choose or name the recipient organization."
        if self.delivery_method == DeliveryMethod.SHIPPING and not self.address_line_1.strip():
            errors["address_line_1"] = "Address line 1 is required for shipping."
        for field in ("donation_amount", "discount_amount"):
            if getattr(self, field) < 0:
                errors[field] = "Amount cannot be negative."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.order_number:
            from apps.bookstore_inventory.services.numbering import generate_order_number

            self.order_number = generate_order_number()
        if self.recipient_organization_id and not self.organization_name:
            self.organization_name = str(self.recipient_organization)
        super().save(*args, **kwargs)

    def recalculate_totals(self, save=True):
        subtotal = self.items.aggregate(
            total=Coalesce(Sum("line_total"), Decimal("0.00"))
        )["total"] or Decimal("0.00")
        paid = self.payments.filter(
            payment_status__in=(PaymentStatus.PARTIAL, PaymentStatus.PAID)
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"] or Decimal("0.00")
        self.subtotal_amount = subtotal
        self.total_amount = max(subtotal + self.donation_amount - self.discount_amount, Decimal("0.00"))
        self.paid_amount = paid
        self.remaining_amount = max(self.total_amount - paid, Decimal("0.00"))
        if paid == 0:
            self.payment_status = PaymentStatus.UNPAID
        elif paid < self.total_amount:
            self.payment_status = PaymentStatus.PARTIAL
        else:
            self.payment_status = PaymentStatus.PAID
        if save:
            self.save(update_fields=(
                "subtotal_amount", "total_amount", "paid_amount",
                "remaining_amount", "payment_status", "updated_at",
            ))


class BookOrderItem(TimeStampedModel):
    order = models.ForeignKey(BookOrder, on_delete=models.CASCADE, related_name="items")
    book_edition = models.ForeignKey(BookEdition, on_delete=models.PROTECT, related_name="order_items")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="order_items")
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    pricing_mode_snapshot = models.CharField(
        max_length=32, choices=PricingMode.choices, default=PricingMode.FIXED_PRICE,
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Book order item"
        verbose_name_plural = "Book order items"

    def __str__(self):
        return f"{self.book_edition} x {self.quantity}"

    def clean(self):
        errors = {}
        if self.quantity <= 0:
            errors["quantity"] = "Quantity must be greater than zero."
        if self.unit_price < 0:
            errors["unit_price"] = "Unit price cannot be negative."
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            errors["location"] = "Location must belong to the selected warehouse."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.pk and not self.unit_price:
            self.unit_price = self.book_edition.fixed_price
        self.line_total = (self.unit_price or Decimal("0.00")) * self.quantity
        if not self.pricing_mode_snapshot:
            self.pricing_mode_snapshot = self.book_edition.pricing_mode
        super().save(*args, **kwargs)


class PaymentRecord(TimeStampedModel):
    order = models.ForeignKey(BookOrder, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=12, default="CAD")
    payment_method = models.CharField(
        max_length=24, choices=PaymentMethod.choices,
        default=PaymentMethod.CASH, db_index=True,
    )
    payment_status = models.CharField(
        max_length=24, choices=PaymentStatus.choices,
        default=PaymentStatus.PAID, db_index=True,
    )
    transaction_reference = models.CharField(max_length=120, blank=True, db_index=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="bookstore_payments_received",
    )
    received_at = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-received_at", "-id")
        verbose_name = "Payment record"
        verbose_name_plural = "Payment records"

    def __str__(self):
        return f"{self.order.order_number} - {self.amount} {self.currency}"

    def clean(self):
        errors = {}
        if self.amount <= 0:
            errors["amount"] = "Payment amount must be greater than zero."
        if self.order_id and self.currency != self.order.currency:
            errors["currency"] = "Payment currency must match the order currency."
        if errors:
            raise ValidationError(errors)
