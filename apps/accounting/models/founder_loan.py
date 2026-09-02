# apps/accounting/models/founder_loan.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .journal_entry import JournalEntry


ZERO = Decimal("0.00")


class FounderLoan(models.Model):
    """Business record for founder financing."""

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

    lender_display_name = models.CharField(
        max_length=255,
    )

    principal_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=10,
        default="CAD",
    )

    loan_date = models.DateField(
        db_index=True,
    )

    description = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )

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

    internal_note = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "-loan_date",
            "-id",
        )
        indexes = [
            models.Index(
                fields=[
                    "status",
                    "loan_date",
                ],
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    principal_amount__gt=0
                ),
                name="founder_loan_principal_positive",
            ),
            models.CheckConstraint(
                check=models.Q(
                    repaid_amount__gte=0
                ),
                name="founder_loan_repaid_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(
                    repaid_amount__lte=models.F(
                        "principal_amount"
                    )
                ),
                name="founder_loan_repaid_lte_principal",
            ),
        ]

    def __str__(self):
        return (
            f"{self.lender_display_name} - "
            f"{self.principal_amount}"
        )

    @property
    def outstanding_amount(self):
        """Return remaining principal."""

        return (
            self.principal_amount or ZERO
        ) - (
            self.repaid_amount or ZERO
        )

    def clean(self):
        """Keep business status aligned with amounts."""

        super().clean()

        principal = (
            self.principal_amount
            or ZERO
        )

        repaid = (
            self.repaid_amount
            or ZERO
        )

        if principal <= ZERO:
            raise ValidationError(
                "principal_amount must be greater than zero."
            )

        if repaid < ZERO:
            raise ValidationError(
                "repaid_amount cannot be negative."
            )

        if repaid > principal:
            raise ValidationError(
                "repaid_amount cannot exceed principal_amount."
            )

        if (
            self.status == self.STATUS_OPEN
            and repaid != ZERO
        ):
            raise ValidationError(
                "An open founder loan must have zero repaid amount."
            )

        if (
            self.status == self.STATUS_PARTIAL
            and not (ZERO < repaid < principal)
        ):
            raise ValidationError(
                "A partially repaid founder loan requires "
                "a repayment between zero and principal."
            )

        if (
            self.status == self.STATUS_REPAID
            and repaid != principal
        ):
            raise ValidationError(
                "A repaid founder loan must have "
                "repaid_amount equal to principal_amount."
            )

        if (
            self.journal_entry_id
            and self.journal_entry.status
            != JournalEntry.STATUS_POSTED
        ):
            raise ValidationError(
                "Founder loan journal entry must be posted."
            )

    def save(self, *args, **kwargs):
        """Validate business state before persistence."""

        self.full_clean()

        return super().save(*args, **kwargs)