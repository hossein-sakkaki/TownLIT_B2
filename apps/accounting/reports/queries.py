# apps/accounting/reports/queries.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

from apps.accounting.models import (
    Account,
    JournalEntry,
    Transaction,
)

from .filters import ReportFilter
from .schemas import (
    FounderBalanceSummary,
    GeneralLedgerReport,
    GeneralLedgerRow,
    MonthlySummaryReport,
    MonthlySummaryRow,
    TrialBalanceReport,
    TrialBalanceRow,
)


ZERO = Decimal("0.00")


def _posted_status_filter(
    include_draft: bool,
) -> Q:
    """Return transaction status filter."""

    if include_draft:
        return ~Q(
            journal_entry__status=JournalEntry.STATUS_VOID
        )

    return Q(
        journal_entry__status=JournalEntry.STATUS_POSTED
    )


def _apply_transaction_date_filters(
    queryset,
    report_filter: ReportFilter,
):
    """Apply period filters."""

    if report_filter.date_from:
        queryset = queryset.filter(
            journal_entry__entry_date__gte=report_filter.date_from
        )

    if report_filter.date_to:
        queryset = queryset.filter(
            journal_entry__entry_date__lte=report_filter.date_to
        )

    return queryset


def _validate_filter(
    report_filter: ReportFilter,
):
    """Validate report dates."""

    if (
        report_filter.date_from
        and report_filter.date_to
        and report_filter.date_from
        > report_filter.date_to
    ):
        raise ValueError(
            "date_from cannot be later than date_to."
        )


def _compute_account_balance(
    normal_balance: str,
    total_debit: Decimal,
    total_credit: Decimal,
) -> Decimal:
    """Compute account balance."""

    total_debit = (
        total_debit
        or ZERO
    )

    total_credit = (
        total_credit
        or ZERO
    )

    if normal_balance == Account.NORMAL_DEBIT:
        return total_debit - total_credit

    return total_credit - total_debit


def build_trial_balance(
    report_filter: ReportFilter,
) -> TrialBalanceReport:
    """Build an as-of trial balance."""

    _validate_filter(report_filter)

    qs = (
        Transaction.objects
        .select_related(
            "account",
            "journal_entry",
        )
        .filter(
            _posted_status_filter(
                report_filter.include_draft
            )
        )
    )

    # Trial balance is cumulative through date_to.
    if report_filter.date_to:
        qs = qs.filter(
            journal_entry__entry_date__lte=report_filter.date_to
        )

    grouped = (
        qs
        .values(
            "account__code",
            "account__name",
            "account__account_type",
            "account__normal_balance",
        )
        .annotate(
            total_debit=Sum("debit"),
            total_credit=Sum("credit"),
        )
        .order_by("account__code")
    )

    rows = []
    total_debit = ZERO
    total_credit = ZERO

    for item in grouped:
        row_debit = (
            item["total_debit"]
            or ZERO
        )

        row_credit = (
            item["total_credit"]
            or ZERO
        )

        balance = _compute_account_balance(
            item["account__normal_balance"],
            row_debit,
            row_credit,
        )

        rows.append(
            TrialBalanceRow(
                account_code=item["account__code"],
                account_name=item["account__name"],
                account_type=item["account__account_type"],
                normal_balance=item["account__normal_balance"],
                total_debit=row_debit,
                total_credit=row_credit,
                balance=balance,
            )
        )

        total_debit += row_debit
        total_credit += row_credit

    return TrialBalanceReport(
        title="Trial Balance",
        date_from=None,
        date_to=report_filter.date_to,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
    )


def build_general_ledger(
    account_code: str,
    report_filter: ReportFilter,
) -> GeneralLedgerReport:
    """Build ledger with correct opening balance."""

    _validate_filter(report_filter)

    account = Account.objects.get(
        code=account_code
    )

    base_qs = (
        Transaction.objects
        .select_related(
            "journal_entry",
            "account",
        )
        .filter(account=account)
        .filter(
            _posted_status_filter(
                report_filter.include_draft
            )
        )
    )

    opening_balance = ZERO

    if report_filter.date_from:
        opening_totals = (
            base_qs
            .filter(
                journal_entry__entry_date__lt=report_filter.date_from
            )
            .aggregate(
                total_debit=Sum("debit"),
                total_credit=Sum("credit"),
            )
        )

        opening_balance = _compute_account_balance(
            account.normal_balance,
            opening_totals["total_debit"] or ZERO,
            opening_totals["total_credit"] or ZERO,
        )

    qs = _apply_transaction_date_filters(
        base_qs,
        report_filter,
    ).order_by(
        "journal_entry__entry_date",
        "journal_entry__id",
        "line_number",
        "id",
    )

    rows = []
    total_debit = ZERO
    total_credit = ZERO
    running_balance = opening_balance

    if report_filter.date_from:
        rows.append(
            GeneralLedgerRow(
                entry_number="OPENING",
                entry_date=report_filter.date_from,
                reference="",
                description="Opening balance before selected period",
                source_app="accounting",
                source_model="computed_opening_balance",
                source_ref="",
                line_memo="",
                debit=ZERO,
                credit=ZERO,
                running_balance=opening_balance,
            )
        )

    for tx in qs:
        debit = (
            tx.debit
            or ZERO
        )

        credit = (
            tx.credit
            or ZERO
        )

        if account.normal_balance == Account.NORMAL_DEBIT:
            running_balance += debit - credit
        else:
            running_balance += credit - debit

        rows.append(
            GeneralLedgerRow(
                entry_number=tx.journal_entry.entry_number,
                entry_date=tx.journal_entry.entry_date,
                reference=tx.journal_entry.reference or "",
                description=tx.journal_entry.description,
                source_app=tx.journal_entry.source_app,
                source_model=tx.journal_entry.source_model,
                source_ref=tx.journal_entry.source_ref,
                line_memo=tx.memo,
                debit=debit,
                credit=credit,
                running_balance=running_balance,
            )
        )

        total_debit += debit
        total_credit += credit

    return GeneralLedgerReport(
        title="General Ledger",
        account_code=account.code,
        account_name=account.name,
        account_type=account.account_type,
        normal_balance=account.normal_balance,
        date_from=report_filter.date_from,
        date_to=report_filter.date_to,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        ending_balance=running_balance,
    )


def build_founder_balance_summary(
    founder_loan_account_code: str,
    founder_withdrawal_account_code: str,
    report_filter: ReportFilter,
) -> FounderBalanceSummary:
    """Build founder financing summary."""

    _validate_filter(report_filter)

    loan_account = Account.objects.get(
        code=founder_loan_account_code
    )

    withdrawal_account = Account.objects.get(
        code=founder_withdrawal_account_code
    )

    qs = (
        Transaction.objects
        .select_related(
            "account",
            "journal_entry",
        )
        .filter(
            account__code__in=[
                founder_loan_account_code,
                founder_withdrawal_account_code,
            ]
        )
        .filter(
            _posted_status_filter(
                report_filter.include_draft
            )
        )
    )

    qs = _apply_transaction_date_filters(
        qs,
        report_filter,
    )

    loan_totals = qs.filter(
        account=loan_account
    ).aggregate(
        debit=Sum("debit"),
        credit=Sum("credit"),
    )

    withdrawal_totals = qs.filter(
        account=withdrawal_account
    ).aggregate(
        debit=Sum("debit"),
        credit=Sum("credit"),
    )

    loan_total = (
        (loan_totals["credit"] or ZERO)
        - (loan_totals["debit"] or ZERO)
    )

    withdrawal_total = (
        (withdrawal_totals["debit"] or ZERO)
        - (withdrawal_totals["credit"] or ZERO)
    )

    net_founder_balance = (
        loan_total
        - withdrawal_total
    )

    return FounderBalanceSummary(
        title="Founder Balance Summary",
        founder_loan_account_code=loan_account.code,
        founder_loan_account_name=loan_account.name,
        founder_withdrawal_account_code=withdrawal_account.code,
        founder_withdrawal_account_name=withdrawal_account.name,
        date_from=report_filter.date_from,
        date_to=report_filter.date_to,
        total_loans=loan_total,
        total_withdrawals=withdrawal_total,
        net_founder_balance=net_founder_balance,
    )


def build_monthly_summary(
    report_filter: ReportFilter,
) -> MonthlySummaryReport:
    """Build monthly revenue and expense summary."""

    _validate_filter(report_filter)

    qs = (
        Transaction.objects
        .select_related(
            "account",
            "journal_entry",
        )
        .filter(
            _posted_status_filter(
                report_filter.include_draft
            )
        )
    )

    qs = _apply_transaction_date_filters(
        qs,
        report_filter,
    )

    monthly = (
        qs
        .annotate(
            period=TruncMonth(
                "journal_entry__entry_date"
            )
        )
        .values(
            "period",
            "account__account_type",
        )
        .annotate(
            debit_total=Sum("debit"),
            credit_total=Sum("credit"),
        )
        .order_by(
            "period",
            "account__account_type",
        )
    )

    buckets = defaultdict(
        lambda: {
            "revenue_total": ZERO,
            "expense_total": ZERO,
        }
    )

    for item in monthly:
        period = item[
            "period"
        ].strftime("%Y-%m")

        debit_total = (
            item["debit_total"]
            or ZERO
        )

        credit_total = (
            item["credit_total"]
            or ZERO
        )

        account_type = (
            item["account__account_type"]
        )

        if account_type == Account.TYPE_REVENUE:
            buckets[
                period
            ]["revenue_total"] += (
                credit_total
                - debit_total
            )

        elif account_type == Account.TYPE_EXPENSE:
            buckets[
                period
            ]["expense_total"] += (
                debit_total
                - credit_total
            )

    rows = []
    total_revenue = ZERO
    total_expense = ZERO
    total_net_result = ZERO

    for period in sorted(
        buckets.keys()
    ):
        revenue_total = (
            buckets[
                period
            ]["revenue_total"]
        )

        expense_total = (
            buckets[
                period
            ]["expense_total"]
        )

        net_result = (
            revenue_total
            - expense_total
        )

        rows.append(
            MonthlySummaryRow(
                period=period,
                revenue_total=revenue_total,
                expense_total=expense_total,
                net_result=net_result,
            )
        )

        total_revenue += revenue_total
        total_expense += expense_total
        total_net_result += net_result

    return MonthlySummaryReport(
        title="Monthly Summary",
        date_from=report_filter.date_from,
        date_to=report_filter.date_to,
        rows=rows,
        total_revenue=total_revenue,
        total_expense=total_expense,
        total_net_result=total_net_result,
    )