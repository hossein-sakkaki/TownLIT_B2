# apps/bookstore_inventory/models/finance.py

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings

from apps.bookstore_inventory.constants import CashEntryDirection, CashEntryType
from apps.bookstore_inventory.models.base import TimeStampedModel


class CashLedgerEntry(TimeStampedModel):
    # Simple cash ledger
    direction = models.CharField(
        max_length=12,
        choices=CashEntryDirection.choices,
        db_index=True,
    )
    entry_type = models.CharField(
        max_length=32,
        choices=CashEntryType.choices,
        db_index=True,
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=12, default="CAD")

    reference_type = models.CharField(max_length=80, blank=True, db_index=True)
    reference_id = models.CharField(max_length=80, blank=True, db_index=True)

    entry_date = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="bookstore_cash_entries_recorded",
    )

    class Meta:
        ordering = ["-entry_date", "-id"]
        verbose_name = "Cash ledger entry"
        verbose_name_plural = "Cash ledger entries"

    def __str__(self):
        return f"{self.get_direction_display()} - {self.amount} {self.currency}"

    def clean(self):
        # Validate ledger amount
        if self.amount <= Decimal("0.00"):
            raise ValidationError({"amount": "Amount must be greater than zero."})