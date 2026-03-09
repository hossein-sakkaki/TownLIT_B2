# apps/accounting/reports/fund_queries.py

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum, Q

from apps.accounting.models import Fund, BudgetLine, Transaction, JournalEntry
from .filters import ReportFilter


ZERO = Decimal("0.00")


def _posted_status_filter(include_draft: bool) -> Q:
    """
    Return entry status filter.
    """

    if include_draft:
        return ~Q(journal_entry__status=JournalEntry.STATUS_VOID)

    return Q(journal_entry__status=JournalEntry.STATUS_POSTED)


def _apply_transaction_date_filters(queryset, report_filter: ReportFilter):
    """
    Apply date filters to transaction queryset.
    """

    if report_filter.date_from:
        queryset = queryset.filter(journal_entry__entry_date__gte=report_filter.date_from)

    if report_filter.date_to:
        queryset = queryset.filter(journal_entry__entry_date__lte=report_filter.date_to)

    return queryset


def build_fund_summary(fund_code: str, report_filter: ReportFilter) -> dict:
    """
    Build summary for one fund.
    """

    fund = Fund.objects.get(code=fund_code)

    qs = Transaction.objects.select_related("account", "journal_entry", "fund").filter(
        fund=fund
    ).filter(
        _posted_status_filter(report_filter.include_draft)
    )
    qs = _apply_transaction_date_filters(qs, report_filter)

    revenue_total = ZERO
    expense_total = ZERO

    grouped = (
        qs.values("account__account_type")
        .annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )
    )

    for item in grouped:
        debit_total = item["debit_total"] or ZERO
        credit_total = item["credit_total"] or ZERO
        account_type = item["account__account_type"]

        if account_type == "revenue":
            revenue_total += credit_total - debit_total

        if account_type == "expense":
            expense_total += debit_total - credit_total

    remaining_balance = revenue_total - expense_total

    return {
        "title": "Fund Summary",
        "fund_code": fund.code,
        "fund_name": fund.name,
        "fund_type": fund.fund_type,
        "is_restricted": fund.is_restricted,
        "date_from": report_filter.date_from,
        "date_to": report_filter.date_to,
        "total_awarded": str(fund.total_awarded or ZERO),
        "revenue_total": str(revenue_total),
        "expense_total": str(expense_total),
        "remaining_balance": str(remaining_balance),
    }


def build_fund_ledger(fund_code: str, report_filter: ReportFilter) -> dict:
    """
    Build ledger for one fund.
    """

    fund = Fund.objects.get(code=fund_code)

    qs = Transaction.objects.select_related("account", "journal_entry", "fund", "budget_line").filter(
        fund=fund
    ).filter(
        _posted_status_filter(report_filter.include_draft)
    )
    qs = _apply_transaction_date_filters(qs, report_filter)
    qs = qs.order_by("journal_entry__entry_date", "journal_entry__id", "line_number", "id")

    rows = []
    revenue_total = ZERO
    expense_total = ZERO

    for tx in qs:
        debit = tx.debit or ZERO
        credit = tx.credit or ZERO

        if tx.account.account_type == "revenue":
            revenue_effect = credit - debit
            expense_effect = ZERO
            revenue_total += revenue_effect
        elif tx.account.account_type == "expense":
            expense_effect = debit - credit
            revenue_effect = ZERO
            expense_total += expense_effect
        else:
            revenue_effect = ZERO
            expense_effect = ZERO

        rows.append(
            {
                "entry_number": tx.journal_entry.entry_number,
                "entry_date": tx.journal_entry.entry_date,
                "account_code": tx.account.code,
                "account_name": tx.account.name,
                "reference": tx.journal_entry.reference,
                "description": tx.journal_entry.description,
                "memo": tx.memo,
                "budget_code": tx.budget_code,
                "debit": str(debit),
                "credit": str(credit),
                "revenue_effect": str(revenue_effect),
                "expense_effect": str(expense_effect),
            }
        )

    return {
        "title": "Fund Ledger",
        "fund_code": fund.code,
        "fund_name": fund.name,
        "date_from": report_filter.date_from,
        "date_to": report_filter.date_to,
        "revenue_total": str(revenue_total),
        "expense_total": str(expense_total),
        "remaining_balance": str(revenue_total - expense_total),
        "rows": rows,
    }


def build_budget_vs_actual(fund_code: str, report_filter: ReportFilter) -> dict:
    """
    Compare budget lines against actual tagged expenses.
    """

    fund = Fund.objects.get(code=fund_code)

    budget_lines = BudgetLine.objects.select_related("budget", "budget__fund").filter(
        budget__fund=fund,
        is_active=True,
        budget__is_active=True,
    ).order_by("budget__code", "sort_order", "code")

    qs = Transaction.objects.select_related("budget_line", "account", "journal_entry").filter(
        fund=fund,
        budget_line__isnull=False,
        account__account_type="expense",
    ).filter(
        _posted_status_filter(report_filter.include_draft)
    )
    qs = _apply_transaction_date_filters(qs, report_filter)

    actuals = defaultdict(lambda: ZERO)

    grouped = (
        qs.values("budget_line_id")
        .annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )
    )

    for item in grouped:
        actuals[item["budget_line_id"]] = (item["debit_total"] or ZERO) - (item["credit_total"] or ZERO)

    rows = []
    total_budget = ZERO
    total_actual = ZERO
    total_remaining = ZERO

    for line in budget_lines:
        approved_amount = line.approved_amount or ZERO
        actual_amount = actuals[line.id]
        remaining_amount = approved_amount - actual_amount

        rows.append(
            {
                "budget_code": line.budget.code,
                "budget_line_code": line.code,
                "budget_line_name": line.name,
                "approved_amount": str(approved_amount),
                "actual_amount": str(actual_amount),
                "remaining_amount": str(remaining_amount),
            }
        )

        total_budget += approved_amount
        total_actual += actual_amount
        total_remaining += remaining_amount

    return {
        "title": "Budget vs Actual",
        "fund_code": fund.code,
        "fund_name": fund.name,
        "date_from": report_filter.date_from,
        "date_to": report_filter.date_to,
        "total_budget": str(total_budget),
        "total_actual": str(total_actual),
        "total_remaining": str(total_remaining),
        "rows": rows,
    }