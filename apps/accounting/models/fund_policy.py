# apps/accounting/models/fund_policy.py

from django.db import models
from .fund import Fund
from .account import Account
from .budget import BudgetLine


class FundPolicy(models.Model):
    """
    Defines posting rules for a specific fund.
    Used to prevent invalid expenses or allocations.
    """

    MODE_OPEN = "open"
    MODE_RESTRICTED = "restricted"

    MODE_CHOICES = (
        (MODE_OPEN, "Open"),
        (MODE_RESTRICTED, "Restricted"),
    )

    fund = models.OneToOneField(
        Fund,
        on_delete=models.CASCADE,
        related_name="policy",
    )

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=MODE_OPEN,
        db_index=True,
        help_text="Open allows all posting accounts. Restricted requires explicit allow rules.",
    )

    # Whether the policy is enforced during posting
    enforce_rules = models.BooleanField(
        default=True,
        help_text="If disabled, reporting still works but hard validation is skipped.",
    )

    # Whether posting date must fall inside fund date range
    enforce_date_window = models.BooleanField(
        default=True,
        help_text="Require journal entry date to be inside fund start/end date.",
    )

    # Whether actual expenses may exceed approved budget
    prevent_budget_overrun = models.BooleanField(
        default=True,
        help_text="Prevent spending beyond approved budget line amount.",
    )

    # Whether expense lines must include a budget line when fund is used
    require_budget_line_for_expenses = models.BooleanField(
        default=False,
        help_text="If true, expense lines tagged to this fund must also include a budget line.",
    )

    # Optional notes for finance/admin users
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("fund__code",)

    def __str__(self):
        return f"Policy for {self.fund.code}"


class FundAllowedAccount(models.Model):
    """
    Explicit list of allowed posting accounts for a restricted fund.
    """

    fund = models.ForeignKey(
        Fund,
        on_delete=models.CASCADE,
        related_name="allowed_accounts",
    )

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="fund_permissions",
    )

    # Optional rule by account type of posting
    allow_revenue = models.BooleanField(default=True)
    allow_expense = models.BooleanField(default=True)
    allow_asset = models.BooleanField(default=False)
    allow_liability = models.BooleanField(default=False)
    allow_equity = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("fund__code", "account__code")
        constraints = [
            models.UniqueConstraint(
                fields=["fund", "account"],
                name="uniq_fund_allowed_account",
            )
        ]

    def __str__(self):
        return f"{self.fund.code} -> {self.account.code}"

    def allows_account_type(self, account_type: str) -> bool:
        """
        Check whether this rule allows the given account type.
        """

        mapping = {
            "revenue": self.allow_revenue,
            "expense": self.allow_expense,
            "asset": self.allow_asset,
            "liability": self.allow_liability,
            "equity": self.allow_equity,
        }
        return mapping.get(account_type, False)


class FundAllowedBudgetLine(models.Model):
    """
    Explicit list of allowed budget lines for a fund.
    """

    fund = models.ForeignKey(
        Fund,
        on_delete=models.CASCADE,
        related_name="allowed_budget_lines",
    )

    budget_line = models.ForeignKey(
        BudgetLine,
        on_delete=models.CASCADE,
        related_name="fund_permissions",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("fund__code", "budget_line__budget__code", "budget_line__code")
        constraints = [
            models.UniqueConstraint(
                fields=["fund", "budget_line"],
                name="uniq_fund_allowed_budget_line",
            )
        ]

    def __str__(self):
        return f"{self.fund.code} -> {self.budget_line.code}"