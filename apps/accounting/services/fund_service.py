# apps/accounting/services/fund_service.py

from apps.accounting.models import Fund, BudgetLine


class FundValidationError(Exception):
    """Raised when fund or budget validation fails."""
    pass


def resolve_fund_by_code(fund_code: str | None):
    """
    Resolve active fund by code.
    """

    if not fund_code:
        return None

    try:
        return Fund.objects.get(code=fund_code, is_active=True)
    except Fund.DoesNotExist as exc:
        raise FundValidationError(f"Fund not found or inactive: {fund_code}") from exc


def resolve_budget_line_by_code(budget_code: str | None):
    """
    Resolve active budget line by code.
    """

    if not budget_code:
        return None

    try:
        return BudgetLine.objects.select_related("budget", "budget__fund").get(
            code=budget_code,
            is_active=True,
            budget__is_active=True,
        )
    except BudgetLine.DoesNotExist as exc:
        raise FundValidationError(f"Budget line not found or inactive: {budget_code}") from exc


def validate_fund_budget_match(fund, budget_line):
    """
    Ensure budget line belongs to the same fund when both are provided.
    """

    if not fund or not budget_line:
        return

    if not budget_line.budget.fund_id:
        raise FundValidationError(
            f"Budget line '{budget_line.code}' is not attached to a fund."
        )

    if budget_line.budget.fund_id != fund.id:
        raise FundValidationError(
            f"Budget line '{budget_line.code}' does not belong to fund '{fund.code}'."
        )