# apps/accounting/models/transaction.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .account import Account
from .budget import BudgetLine
from .fund import Fund
from .journal_entry import JournalEntry


class Transaction(models.Model):
    """One debit or credit line inside a journal entry."""

    journal_entry = models.ForeignKey(
        JournalEntry,
        related_name="transactions",
        on_delete=models.PROTECT,
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

    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    budget_line = models.ForeignKey(
        BudgetLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    # Historical snapshots
    fund_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    budget_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ("line_number", "id")
        indexes = [
            models.Index(
                fields=["account", "journal_entry"],
            ),
            models.Index(fields=["fund"]),
            models.Index(fields=["budget_line"]),
            models.Index(fields=["fund_code"]),
            models.Index(fields=["budget_code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "journal_entry",
                    "line_number",
                ],
                name="uniq_journal_entry_line_number",
            ),
            models.CheckConstraint(
                check=(
                    (
                        Q(debit__gt=0)
                        & Q(credit=0)
                    )
                    |
                    (
                        Q(credit__gt=0)
                        & Q(debit=0)
                    )
                ),
                name="transaction_exactly_one_side_positive",
            ),
            models.CheckConstraint(
                check=(
                    Q(debit__gte=0)
                    & Q(credit__gte=0)
                ),
                name="transaction_non_negative_amounts",
            ),
        ]

    def __str__(self):
        return (
            f"{self.journal_entry.entry_number} | "
            f"{self.account.code}"
        )

    def save(self, *args, **kwargs):
        """Protect posted transaction lines."""

        if self.pk:
            existing = (
                type(self).objects
                .select_related("journal_entry")
                .get(pk=self.pk)
            )

            if (
                existing.journal_entry.status
                == JournalEntry.STATUS_POSTED
            ):
                raise ValidationError(
                    "Transactions belonging to a posted "
                    "journal entry are immutable."
                )

        elif (
            self.journal_entry_id
            and self.journal_entry.status
            == JournalEntry.STATUS_POSTED
        ):
            raise ValidationError(
                "Transaction lines for posted entries "
                "must be created through accounting services."
            )

        self.fund_code = (
            self.fund.code
            if self.fund
            else ""
        )

        self.budget_code = (
            self.budget_line.code
            if self.budget_line
            else ""
        )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Protect posted ledger lines."""

        if (
            self.journal_entry.status
            == JournalEntry.STATUS_POSTED
        ):
            raise ValidationError(
                "Transactions belonging to a posted "
                "journal entry cannot be deleted."
            )

        return super().delete(*args, **kwargs)