# apps/accounting/models/account.py

from django.core.exceptions import ValidationError
from django.db import models
from .account_category import AccountCategory


class Account(models.Model):
    """
    Represents a ledger account in the chart of accounts.
    Supports both parent/group accounts and posting accounts.
    """

    TYPE_ASSET = "asset"
    TYPE_LIABILITY = "liability"
    TYPE_EQUITY = "equity"
    TYPE_REVENUE = "revenue"
    TYPE_EXPENSE = "expense"

    ACCOUNT_TYPE_CHOICES = (
        (TYPE_ASSET, "Asset"),
        (TYPE_LIABILITY, "Liability"),
        (TYPE_EQUITY, "Equity"),
        (TYPE_REVENUE, "Revenue"),
        (TYPE_EXPENSE, "Expense"),
    )

    NORMAL_DEBIT = "debit"
    NORMAL_CREDIT = "credit"

    NORMAL_BALANCE_CHOICES = (
        (NORMAL_DEBIT, "Debit"),
        (NORMAL_CREDIT, "Credit"),
    )

    name = models.CharField(max_length=255)

    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Unique account code",
    )

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        db_index=True,
    )

    category = models.ForeignKey(
        AccountCategory,
        on_delete=models.PROTECT,
        related_name="accounts",
    )

    # Parent/group account
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )

    # Expected natural balance
    normal_balance = models.CharField(
        max_length=10,
        choices=NORMAL_BALANCE_CHOICES,
        help_text="Normal balance side for reporting logic",
    )

    # Group accounts should not accept postings directly
    allows_posting = models.BooleanField(
        default=True,
        help_text="Whether journal lines can be posted directly to this account",
    )

    # Protect key seeded accounts
    is_system = models.BooleanField(
        default=False,
        help_text="System account protected from accidental changes",
    )

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        indexes = [
            models.Index(fields=["account_type", "is_active"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """
        Validate account hierarchy rules.
        """

        if self.parent_id and self.parent_id == self.id:
            raise ValidationError("An account cannot be its own parent.")

        if self.parent and self.parent.allows_posting:
            raise ValidationError(
                "Parent account should normally be a non-posting group account."
            )

        # Prevent category/type mismatch with parent
        if self.parent and self.parent.account_type != self.account_type:
            raise ValidationError(
                "Child account must have the same account_type as its parent."
            )

        # Prevent deep self-referencing loops
        ancestor = self.parent
        while ancestor:
            if ancestor.id == self.id:
                raise ValidationError("Circular account hierarchy is not allowed.")
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)