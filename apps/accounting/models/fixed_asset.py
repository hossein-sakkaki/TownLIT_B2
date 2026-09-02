# apps/accounting/models/fixed_asset.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .account import Account
from .bank import BankAccount
from .budget import BudgetLine
from .fund import Fund
from .journal_entry import JournalEntry


ZERO = Decimal("0.00")


class FixedAsset(models.Model):
    """Capital asset tracked separately from ordinary operating expenses."""

    STATUS_ACTIVE = "active"
    STATUS_FULLY_DEPRECIATED = "fully_depreciated"
    STATUS_DISPOSED = "disposed"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_FULLY_DEPRECIATED, "Fully Depreciated"),
        (STATUS_DISPOSED, "Disposed"),
    )

    METHOD_STRAIGHT_LINE = "straight_line"
    METHOD_CHOICES = (
        (METHOD_STRAIGHT_LINE, "Straight Line"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    asset_number = models.CharField(max_length=40, unique=True, editable=False, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    asset_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="fixed_assets",
    )
    accumulated_depreciation_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="fixed_assets_accumulated_depreciation",
    )
    depreciation_expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="fixed_assets_depreciation_expense",
    )
    acquisition_bank_account = models.ForeignKey(
        BankAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_asset_purchases",
        help_text="Bank account used for direct purchases. Blank when acquired through Accounts Payable.",
    )

    purchase_date = models.DateField(db_index=True)
    placed_in_service_date = models.DateField(db_index=True)
    cost = models.DecimalField(max_digits=14, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    useful_life_months = models.PositiveIntegerField()
    depreciation_method = models.CharField(
        max_length=30,
        choices=METHOD_CHOICES,
        default=METHOD_STRAIGHT_LINE,
    )

    vendor_name = models.CharField(max_length=255, blank=True, default="")
    reference = models.CharField(max_length=255, blank=True, default="", db_index=True)
    serial_number = models.CharField(max_length=255, blank=True, default="", db_index=True)

    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_assets",
    )
    budget_line = models.ForeignKey(
        BudgetLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_assets",
    )

    acquisition_journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fixed_asset_acquisitions",
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    disposed_on = models.DateField(null=True, blank=True)
    disposal_note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_fixed_assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-purchase_date", "asset_number")
        indexes = [
            models.Index(fields=["status", "placed_in_service_date"]),
            models.Index(fields=["asset_account", "status"]),
            models.Index(fields=["fund", "status"]),
        ]

    def __str__(self):
        return f"{self.asset_number} - {self.name}"

    @property
    def depreciable_amount(self):
        return max((self.cost or ZERO) - (self.salvage_value or ZERO), ZERO)

    @property
    def accumulated_depreciation(self):
        if not self.pk:
            return ZERO
        return sum(
            (item.amount for item in self.depreciation_entries.all()),
            ZERO,
        )

    @property
    def book_value(self):
        return max((self.cost or ZERO) - self.accumulated_depreciation, ZERO)

    @property
    def monthly_depreciation_amount(self):
        if not self.useful_life_months:
            return ZERO
        return (self.depreciable_amount / Decimal(self.useful_life_months)).quantize(
            Decimal("0.01")
        )

    def clean(self):
        if self.cost is not None and self.cost <= ZERO:
            raise ValidationError({"cost": "Asset cost must be greater than zero."})

        if self.salvage_value is not None and self.salvage_value < ZERO:
            raise ValidationError({"salvage_value": "Salvage value cannot be negative."})

        if (
            self.cost is not None
            and self.salvage_value is not None
            and self.salvage_value >= self.cost
        ):
            raise ValidationError({"salvage_value": "Salvage value must be less than asset cost."})

        if self.placed_in_service_date and self.purchase_date:
            if self.placed_in_service_date < self.purchase_date:
                raise ValidationError(
                    {"placed_in_service_date": "Placed-in-service date cannot be before purchase date."}
                )

        if self.asset_account_id:
            if self.asset_account.account_type != Account.TYPE_ASSET:
                raise ValidationError({"asset_account": "Asset account must be an ASSET account."})
            if not self.asset_account.is_active or not self.asset_account.allows_posting:
                raise ValidationError({"asset_account": "Asset account must be active and postable."})

        if self.accumulated_depreciation_account_id:
            account = self.accumulated_depreciation_account
            if account.account_type != Account.TYPE_ASSET:
                raise ValidationError(
                    {"accumulated_depreciation_account": "Accumulated depreciation must use an ASSET contra-account."}
                )
            if account.normal_balance != Account.NORMAL_CREDIT:
                raise ValidationError(
                    {"accumulated_depreciation_account": "Accumulated depreciation account must have a credit normal balance."}
                )
            if not account.is_active or not account.allows_posting:
                raise ValidationError(
                    {"accumulated_depreciation_account": "Accumulated depreciation account must be active and postable."}
                )

        if self.depreciation_expense_account_id:
            account = self.depreciation_expense_account
            if account.account_type != Account.TYPE_EXPENSE:
                raise ValidationError(
                    {"depreciation_expense_account": "Depreciation expense account must be an EXPENSE account."}
                )
            if not account.is_active or not account.allows_posting:
                raise ValidationError(
                    {"depreciation_expense_account": "Depreciation expense account must be active and postable."}
                )

        if self.budget_line_id and self.fund_id:
            budget_fund_id = self.budget_line.budget.fund_id
            if budget_fund_id and budget_fund_id != self.fund_id:
                raise ValidationError(
                    {"budget_line": "Budget line must belong to the selected fund."}
                )

        if self.status == self.STATUS_DISPOSED and not self.disposed_on:
            raise ValidationError({"disposed_on": "Disposed assets require a disposal date."})

    def save(self, *args, **kwargs):
        if not self.asset_number:
            self.asset_number = f"FA-{str(self.public_id).split('-')[0].upper()}"
        self.full_clean()
        return super().save(*args, **kwargs)


class FixedAssetDepreciation(models.Model):
    """One posted depreciation event for a fixed asset and accounting period."""

    asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.PROTECT,
        related_name="depreciation_entries",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="fixed_asset_depreciation",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posted_fixed_asset_depreciation",
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period_end", "asset__asset_number")
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "period_start", "period_end"],
                name="uniq_fixed_asset_depreciation_period",
            ),
        ]
        indexes = [
            models.Index(fields=["period_end"]),
            models.Index(fields=["asset", "period_end"]),
        ]

    def __str__(self):
        return f"{self.asset.asset_number} | {self.period_end} | {self.amount}"

    def clean(self):
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError("Depreciation period end cannot be before period start.")
        if self.amount is not None and self.amount <= ZERO:
            raise ValidationError({"amount": "Depreciation amount must be greater than zero."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted depreciation records cannot be deleted. Reverse the journal entry instead.")
