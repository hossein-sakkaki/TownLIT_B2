# apps/accounting/models/transaction.py

from django.db import models
from django.db.models import Q
from .journal_entry import JournalEntry
from .account import Account
from .fund import Fund
from .budget import BudgetLine


class Transaction(models.Model):
    """
    One debit or credit line inside a journal entry.
    """

    journal_entry = models.ForeignKey(
        JournalEntry,
        related_name="transactions",
        on_delete=models.CASCADE,
    )

    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line order inside the journal entry",
    )

    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    memo = models.TextField(blank=True)

    # Real fund linkage
    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    # Real budget-line linkage
    budget_line = models.ForeignKey(
        BudgetLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    # Lightweight snapshots for safe exports/history
    fund_code = models.CharField(max_length=50, blank=True, default="")
    budget_code = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("line_number", "id")
        indexes = [
            models.Index(fields=["account", "journal_entry"]),
            models.Index(fields=["fund"]),
            models.Index(fields=["budget_line"]),
            models.Index(fields=["fund_code"]),
            models.Index(fields=["budget_code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["journal_entry", "line_number"],
                name="uniq_journal_entry_line_number",
            ),
            models.CheckConstraint(
                check=(
                    (Q(debit__gt=0) & Q(credit=0)) |
                    (Q(credit__gt=0) & Q(debit=0))
                ),
                name="transaction_exactly_one_side_positive",
            ),
            models.CheckConstraint(
                check=Q(debit__gte=0) & Q(credit__gte=0),
                name="transaction_non_negative_amounts",
            ),
        ]

    def __str__(self):
        return f"{self.journal_entry.entry_number} | {self.account.code}"

    def save(self, *args, **kwargs):
        """
        Keep snapshot codes in sync with linked objects.
        """

        if self.fund and not self.fund_code:
            self.fund_code = self.fund.code

        if self.budget_line and not self.budget_code:
            self.budget_code = self.budget_line.code

        return super().save(*args, **kwargs)