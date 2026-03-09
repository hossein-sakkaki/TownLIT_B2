# apps/accounting/models/founder_loan.py

from decimal import Decimal

from django.conf import settings
from django.db import models
from .journal_entry import JournalEntry


class FounderLoan(models.Model):
    """
    Domain record for money personally advanced by a founder
    to support the organization.

    Accounting truth remains in the journal entry.
    This model exists for business workflow and reporting.
    """

    STATUS_OPEN = "open"
    STATUS_PARTIAL = "partial"
    STATUS_REPAID = "repaid"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_PARTIAL, "Partially Repaid"),
        (STATUS_REPAID, "Repaid"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    lender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="founder_loans",
    )

    lender_display_name = models.CharField(max_length=255)

    principal_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    currency = models.CharField(max_length=10, default="CAD")

    loan_date = models.DateField(db_index=True)

    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )

    # Initial accounting entry for the loan
    journal_entry = models.OneToOneField(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="founder_loan_record",
    )

    repaid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    internal_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-loan_date", "-id")
        indexes = [
            models.Index(fields=["status", "loan_date"]),
        ]

    def __str__(self):
        return f"{self.lender_display_name} - {self.principal_amount}"

    @property
    def outstanding_amount(self):
        """
        Remaining balance for the loan record.
        """
        return (self.principal_amount or Decimal("0.00")) - (
            self.repaid_amount or Decimal("0.00")
        )