# apps/accounting/services/fund_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from apps.accounting.models import (
    Budget,
    BudgetLine,
    Fund,
)


class FundValidationError(Exception):
    """Raised when fund or budget validation fails."""

    pass


def resolve_fund_by_code(
    fund_code: str | None,
):
    """Resolve one active fund."""

    fund_code = (
        fund_code or ""
    ).strip()

    if not fund_code:
        return None

    try:
        return Fund.objects.get(
            code=fund_code,
            is_active=True,
        )
    except Fund.DoesNotExist as exc:
        raise FundValidationError(
            f"Fund not found or inactive: {fund_code}"
        ) from exc


def resolve_budget_line_by_code(
    budget_code: str | None,
    *,
    fund_code: str | None = None,
    budget_plan_code: str | None = None,
):
    """Resolve a budget line without code ambiguity."""

    budget_code = (
        budget_code or ""
    ).strip()

    fund_code = (
        fund_code or ""
    ).strip()

    budget_plan_code = (
        budget_plan_code or ""
    ).strip()

    if not budget_code:
        return None

    qs = (
        BudgetLine.objects
        .select_related(
            "budget",
            "budget__fund",
        )
        .filter(
            code=budget_code,
            is_active=True,
            budget__is_active=True,
            budget__status=Budget.STATUS_ACTIVE,
        )
    )

    if fund_code:
        qs = qs.filter(
            budget__fund__code=fund_code
        )

    if budget_plan_code:
        qs = qs.filter(
            budget__code=budget_plan_code
        )

    matches = list(
        qs.order_by("id")[:2]
    )

    if not matches:
        raise FundValidationError(
            f"Budget line not found or inactive: {budget_code}"
        )

    if len(matches) > 1:
        raise FundValidationError(
            f"Budget line code '{budget_code}' is ambiguous. "
            "Provide fund_code or budget_plan_code."
        )

    return matches[0]


def validate_fund_budget_match(
    fund,
    budget_line,
):
    """Ensure budget line and fund agree."""

    if not fund or not budget_line:
        return

    if not budget_line.budget.fund_id:
        raise FundValidationError(
            f"Budget line '{budget_line.code}' "
            "is not attached to a fund."
        )

    if budget_line.budget.fund_id != fund.id:
        raise FundValidationError(
            f"Budget line '{budget_line.code}' "
            f"does not belong to fund '{fund.code}'."
        )