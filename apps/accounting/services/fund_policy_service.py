# apps/accounting/services/fund_policy_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from decimal import Decimal

from django.db.models import Sum

from apps.accounting.models import (
    Account,
    BudgetLine,
    Fund,
    FundAllowedAccount,
    FundAllowedBudgetLine,
    FundPolicy,
    Transaction,
)


ZERO = Decimal("0.00")


class FundPolicyValidationError(Exception):
    """Raised when a posting violates a fund policy."""

    pass


def validate_fund_posting_policy(
    *,
    fund: Fund | None,
    account: Account,
    budget_line: BudgetLine | None,
    entry_date,
    debit: Decimal,
    credit: Decimal,
    check_budget_limit: bool = True,
):
    """Validate one fund-aware journal line."""

    if not fund:
        return

    if not fund.is_active:
        raise FundPolicyValidationError(f"Fund '{fund.code}' is inactive.")

    if fund.status != Fund.STATUS_ACTIVE:
        raise FundPolicyValidationError(
            f"Fund '{fund.code}' is not active for posting."
        )

    policy = getattr(fund, "policy", None)

    # Date rules apply even when detailed rules are disabled.
    _validate_fund_date_window(
        fund=fund,
        policy=policy,
        entry_date=entry_date,
    )

    if not policy or not policy.enforce_rules:
        return

    if policy.mode == FundPolicy.MODE_RESTRICTED:
        _validate_allowed_account(
            fund=fund,
            account=account,
        )

        if budget_line:
            _validate_allowed_budget_line(
                fund=fund,
                budget_line=budget_line,
            )

    if account.account_type != Account.TYPE_EXPENSE:
        return

    if policy.require_budget_line_for_expenses and not budget_line:
        raise FundPolicyValidationError(
            f"Expense postings for fund '{fund.code}' require a budget line."
        )

    if budget_line and policy.prevent_budget_overrun and check_budget_limit:
        validate_fund_budget_limit(
            fund=fund,
            budget_line=budget_line,
            posting_amount=debit - credit,
        )


def validate_fund_budget_limit(
    *,
    fund: Fund,
    budget_line: BudgetLine,
    posting_amount: Decimal,
):
    """Validate the final aggregated expense effect."""

    policy = getattr(fund, "policy", None)

    if not policy:
        return

    if not policy.enforce_rules:
        return

    if not policy.prevent_budget_overrun:
        return

    _validate_budget_limit(
        fund=fund,
        budget_line=budget_line,
        posting_amount=posting_amount,
    )


def _validate_fund_date_window(
    *,
    fund: Fund,
    policy: FundPolicy | None,
    entry_date,
):
    """Validate the fund date window."""

    if not policy or not policy.enforce_date_window:
        return

    if fund.start_date and entry_date < fund.start_date:
        raise FundPolicyValidationError(
            f"Entry date {entry_date} is before fund '{fund.code}' start date {fund.start_date}."
        )

    if fund.end_date and entry_date > fund.end_date:
        raise FundPolicyValidationError(
            f"Entry date {entry_date} is after fund '{fund.code}' end date {fund.end_date}."
        )


def _validate_allowed_account(
    *,
    fund: Fund,
    account: Account,
):
    """Validate an allowed account."""

    try:
        rule = FundAllowedAccount.objects.select_related("account").get(
            fund=fund,
            account=account,
        )
    except FundAllowedAccount.DoesNotExist as exc:
        raise FundPolicyValidationError(
            f"Account '{account.code}' is not allowed for fund '{fund.code}'."
        ) from exc

    if not rule.allows_account_type(account.account_type):
        raise FundPolicyValidationError(
            f"Account '{account.code}' is not allowed for account type "
            f"'{account.account_type}' under fund '{fund.code}'."
        )


def _validate_allowed_budget_line(
    *,
    fund: Fund,
    budget_line: BudgetLine,
):
    """Validate an allowed budget line."""

    exists = FundAllowedBudgetLine.objects.filter(
        fund=fund,
        budget_line=budget_line,
    ).exists()

    if not exists:
        raise FundPolicyValidationError(
            f"Budget line '{budget_line.code}' is not allowed for fund '{fund.code}'."
        )


def _validate_budget_limit(
    *,
    fund: Fund,
    budget_line: BudgetLine,
    posting_amount: Decimal,
):
    """Prevent expense posting beyond the approved budget."""

    posting_amount = posting_amount or ZERO

    if posting_amount <= ZERO:
        return

    totals = Transaction.objects.filter(
        fund=fund,
        budget_line=budget_line,
        account__account_type=Account.TYPE_EXPENSE,
        journal_entry__status="posted",
    ).aggregate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )

    actual_spent = (
        (totals["total_debit"] or ZERO)
        - (totals["total_credit"] or ZERO)
    )

    approved_amount = budget_line.approved_amount or ZERO
    projected_total = actual_spent + posting_amount

    if projected_total > approved_amount:
        raise FundPolicyValidationError(
            f"Budget overrun for budget line '{budget_line.code}'. "
            f"Approved={approved_amount}, Current={actual_spent}, "
            f"New={posting_amount}, Projected={projected_total}."
        )