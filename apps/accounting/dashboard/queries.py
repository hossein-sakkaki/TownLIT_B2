# apps/accounting/dashboard/queries.py

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth

from apps.accounting.models import (
    Account,
    Transaction,
    JournalEntry,
    Fund,
    BankReconciliationSession,
)
from .schemas import (
    DashboardKPI,
    MonthlyTrendPoint,
    FundBalanceRow,
    ReconciliationAlertRow,
    DashboardPayload,
)


ZERO = Decimal("0.00")


def build_dashboard_payload() -> DashboardPayload:
    """
    Build financial dashboard payload from accounting data.
    """

    payload = DashboardPayload(
        currency="CAD",
        kpis=_build_kpis(),
        monthly_trend=_build_monthly_trend(),
        fund_balances=_build_fund_balances(),
        reconciliation_alerts=_build_reconciliation_alerts(),
    )
    return payload


def _build_kpis() -> list[DashboardKPI]:
    """
    Build top KPI cards.
    """

    cash_position = _calculate_cash_position()
    founder_balance = _calculate_founder_balance()
    open_fund_balance = _calculate_total_open_fund_balance()
    unreconciled_count = _count_unreconciled_sessions()

    return [
        DashboardKPI(
            key="cash_position",
            label="Cash Position",
            value=str(cash_position),
            currency="CAD",
            status="good" if cash_position >= ZERO else "warning",
        ),
        DashboardKPI(
            key="founder_balance",
            label="Net Founder Balance",
            value=str(founder_balance),
            currency="CAD",
            status="warning" if founder_balance > ZERO else "neutral",
        ),
        DashboardKPI(
            key="open_fund_balance",
            label="Open Fund Balance",
            value=str(open_fund_balance),
            currency="CAD",
            status="good",
        ),
        DashboardKPI(
            key="unreconciled_sessions",
            label="Open Reconciliation Alerts",
            value=str(unreconciled_count),
            currency="",
            status="warning" if unreconciled_count > 0 else "good",
        ),
    ]


def _calculate_cash_position() -> Decimal:
    """
    Sum balances for active asset accounts linked to cash/bank.
    """

    bank_accounts = Account.objects.filter(
        code__in=["1000", "1010", "1020", "1030"],
        is_active=True,
    )

    total = ZERO

    for account in bank_accounts:
        totals = Transaction.objects.filter(
            account=account,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        ).aggregate(
            total_debit=Sum("debit"),
            total_credit=Sum("credit"),
        )

        total_debit = totals["total_debit"] or ZERO
        total_credit = totals["total_credit"] or ZERO

        if account.normal_balance == Account.NORMAL_DEBIT:
            total += total_debit - total_credit
        else:
            total += total_credit - total_debit

    return total


def _calculate_founder_balance() -> Decimal:
    """
    Founder loans minus founder withdrawals.
    """

    loan_account = Account.objects.filter(code="2110").first()
    withdrawal_account = Account.objects.filter(code="3300").first()

    loan_total = ZERO
    withdrawal_total = ZERO

    if loan_account:
        totals = Transaction.objects.filter(
            account=loan_account,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        ).aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        loan_total = (totals["total_credit"] or ZERO) - (totals["total_debit"] or ZERO)

    if withdrawal_account:
        totals = Transaction.objects.filter(
            account=withdrawal_account,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        ).aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
        withdrawal_total = (totals["total_debit"] or ZERO) - (totals["total_credit"] or ZERO)

    return loan_total - withdrawal_total


def _calculate_total_open_fund_balance() -> Decimal:
    """
    Aggregate remaining balances of active funds.
    """

    total = ZERO

    for row in _build_fund_balances():
        total += row.remaining_balance

    return total


def _count_unreconciled_sessions() -> int:
    """
    Count sessions with non-zero difference and not completed.
    """

    return BankReconciliationSession.objects.filter(
        ~Q(unreconciled_difference=0),
        status__in=[
            BankReconciliationSession.STATUS_OPEN,
            BankReconciliationSession.STATUS_LOCKED,
        ],
    ).count()


def _build_monthly_trend() -> list[MonthlyTrendPoint]:
    """
    Build monthly revenue/expense trend.
    """

    qs = Transaction.objects.filter(
        journal_entry__status=JournalEntry.STATUS_POSTED
    ).annotate(
        period=TruncMonth("journal_entry__entry_date")
    ).values(
        "period",
        "account__account_type",
    ).annotate(
        debit_total=Sum("debit"),
        credit_total=Sum("credit"),
    ).order_by("period", "account__account_type")

    buckets = defaultdict(lambda: {"revenue_total": ZERO, "expense_total": ZERO})

    for item in qs:
        period = item["period"].strftime("%Y-%m")
        debit_total = item["debit_total"] or ZERO
        credit_total = item["credit_total"] or ZERO
        account_type = item["account__account_type"]

        if account_type == "revenue":
            buckets[period]["revenue_total"] += credit_total - debit_total

        if account_type == "expense":
            buckets[period]["expense_total"] += debit_total - credit_total

    rows = []

    for period in sorted(buckets.keys()):
        revenue_total = buckets[period]["revenue_total"]
        expense_total = buckets[period]["expense_total"]

        rows.append(
            MonthlyTrendPoint(
                period=period,
                revenue_total=revenue_total,
                expense_total=expense_total,
                net_result=revenue_total - expense_total,
            )
        )

    return rows


def _build_fund_balances() -> list[FundBalanceRow]:
    """
    Build balance summary for active funds.
    """

    funds = Fund.objects.filter(is_active=True).order_by("code")
    rows = []

    for fund in funds:
        txs = Transaction.objects.filter(
            fund=fund,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        )

        revenue_total = ZERO
        expense_total = ZERO

        grouped = txs.values("account__account_type").annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )

        for item in grouped:
            debit_total = item["debit_total"] or ZERO
            credit_total = item["credit_total"] or ZERO
            account_type = item["account__account_type"]

            if account_type == "revenue":
                revenue_total += credit_total - debit_total

            if account_type == "expense":
                expense_total += debit_total - credit_total

        rows.append(
            FundBalanceRow(
                fund_code=fund.code,
                fund_name=fund.name,
                fund_type=fund.fund_type,
                revenue_total=revenue_total,
                expense_total=expense_total,
                remaining_balance=revenue_total - expense_total,
                total_awarded=fund.total_awarded or ZERO,
            )
        )

    return rows


def _build_reconciliation_alerts() -> list[ReconciliationAlertRow]:
    """
    Build reconciliation alerts for sessions with differences.
    """

    sessions = BankReconciliationSession.objects.select_related("bank_account").filter(
        ~Q(unreconciled_difference=0),
        status__in=[
            BankReconciliationSession.STATUS_OPEN,
            BankReconciliationSession.STATUS_LOCKED,
        ],
    ).order_by("-period_end", "-id")[:10]

    return [
        ReconciliationAlertRow(
            bank_account_code=session.bank_account.code,
            bank_account_name=session.bank_account.name,
            period_start=session.period_start.isoformat(),
            period_end=session.period_end.isoformat(),
            unreconciled_difference=session.unreconciled_difference,
            status=session.status,
        )
        for session in sessions
    ]