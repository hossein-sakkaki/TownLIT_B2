# apps/accounting/models/bank.py

from django.db import models

from .account import Account
from .bank_institution import BankInstitution


class BankAccount(models.Model):
    """
    Represents a real-world bank or payment account
    used for reconciliation.
    """

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_CLOSED, "Closed"),
    )

    TYPE_OPERATING = "operating"
    TYPE_SAVINGS = "savings"
    TYPE_GRANT = "grant"
    TYPE_RESERVE = "reserve"
    TYPE_PAYMENT_SETTLEMENT = "payment_settlement"
    TYPE_OTHER = "other"

    ACCOUNT_TYPE_CHOICES = (
        (TYPE_OPERATING, "Operating"),
        (TYPE_SAVINGS, "Savings"),
        (TYPE_GRANT, "Grant"),
        (TYPE_RESERVE, "Reserve"),
        (TYPE_PAYMENT_SETTLEMENT, "Payment Settlement"),
        (TYPE_OTHER, "Other"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique bank account code",
    )

    name = models.CharField(max_length=255)

    institution = models.ForeignKey(
        BankInstitution,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
    )

    account_type = models.CharField(
        max_length=30,
        choices=ACCOUNT_TYPE_CHOICES,
        default=TYPE_OPERATING,
        db_index=True,
    )

    institution_name_snapshot = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Snapshot of institution name for exports/history",
    )

    account_holder_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    account_number_masked = models.CharField(
        max_length=50,
        blank=True,
        help_text="Masked account number only",
    )

    transit_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    routing_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    iban = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    currency = models.CharField(max_length=10, default="CAD")

    # Link to ledger account
    ledger_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    opened_on = models.DateField(null=True, blank=True)
    closed_on = models.DateField(null=True, blank=True)

    note = models.TextField(blank=True)

    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        indexes = [
            models.Index(fields=["institution", "status"]),
            models.Index(fields=["ledger_account", "status"]),
            models.Index(fields=["account_type", "status"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        """
        Keep institution snapshot in sync.
        """

        if self.institution and not self.institution_name_snapshot:
            self.institution_name_snapshot = self.institution.name

        return super().save(*args, **kwargs)