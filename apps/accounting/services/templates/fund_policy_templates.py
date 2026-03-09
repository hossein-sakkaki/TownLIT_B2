# apps/accounting/services/templates/fund_policy_templates.py

from apps.accounting.models import (
    Fund,
    Account,
    BudgetLine,
    FundPolicy,
    FundAllowedAccount,
    FundAllowedBudgetLine,
)


def create_restricted_fund_policy(
    *,
    fund_code: str,
    allowed_account_codes: list[str],
    allowed_budget_line_ids: list[int] | None = None,
    require_budget_line_for_expenses: bool = True,
    prevent_budget_overrun: bool = True,
    enforce_date_window: bool = True,
):
    """
    Create or update a restricted policy for a fund.
    """

    fund = Fund.objects.get(code=fund_code)

    policy, _ = FundPolicy.objects.update_or_create(
        fund=fund,
        defaults={
            "mode": FundPolicy.MODE_RESTRICTED,
            "enforce_rules": True,
            "enforce_date_window": enforce_date_window,
            "prevent_budget_overrun": prevent_budget_overrun,
            "require_budget_line_for_expenses": require_budget_line_for_expenses,
        },
    )

    FundAllowedAccount.objects.filter(fund=fund).delete()
    FundAllowedBudgetLine.objects.filter(fund=fund).delete()

    accounts = Account.objects.filter(code__in=allowed_account_codes, is_active=True)

    for account in accounts:
        FundAllowedAccount.objects.create(
            fund=fund,
            account=account,
            allow_revenue=(account.account_type == "revenue"),
            allow_expense=(account.account_type == "expense"),
            allow_asset=(account.account_type == "asset"),
            allow_liability=(account.account_type == "liability"),
            allow_equity=(account.account_type == "equity"),
        )

    if allowed_budget_line_ids:
        budget_lines = BudgetLine.objects.filter(id__in=allowed_budget_line_ids, is_active=True)
        for line in budget_lines:
            FundAllowedBudgetLine.objects.create(
                fund=fund,
                budget_line=line,
            )

    return policy