# apps/accounting/services/operations_dashboard_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-02.
# Last Update by Hossein Sakkaki on 2026-09-02.
#

from datetime import timedelta
from decimal import Decimal

from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone

from apps.accounting.models import (
    AccountingPeriod,
    BankAccount,
    BankReconciliationSession,
    BankStatementImport,
    BankStatementLine,
    Budget,
    BudgetLine,
    FixedAsset,
    FixedAssetDepreciation,
    Fund,
    FundPolicy,
    JournalEntry,
    PayRun,
    PayStub,
    PayrollRemittance,
    Transaction,
    VendorBill,
    CustomerInvoice,
)
from apps.accounting.services.fund_monitoring_service import build_budget_line_metrics


ZERO = Decimal("0.00")
BUDGET_WARNING_RATIO = Decimal("0.80")


def _sum_field(queryset, field_name: str) -> Decimal:
    return queryset.aggregate(total=Sum(field_name))["total"] or ZERO


def _outstanding_bill_total(queryset) -> Decimal:
    return _sum_field(queryset, "total_amount") - _sum_field(queryset, "amount_paid")


def _outstanding_invoice_total(queryset) -> Decimal:
    return _sum_field(queryset, "total_amount") - _sum_field(queryset, "amount_received")


def _current_month_period(today):
    return (
        AccountingPeriod.objects.filter(
            period_type=AccountingPeriod.PERIOD_TYPE_MONTH,
            start_date__lte=today,
            end_date__gte=today,
        )
        .order_by("start_date", "id")
        .first()
    )


def _cash_metrics() -> dict:
    bank_accounts = list(
        BankAccount.objects.filter(
            status=BankAccount.STATUS_ACTIVE,
            is_active=True,
        )
        .select_related("institution", "ledger_account")
        .order_by("-is_primary", "code")
    )

    ledger_ids = sorted({item.ledger_account_id for item in bank_accounts})
    balances = {ledger_id: ZERO for ledger_id in ledger_ids}

    if ledger_ids:
        rows = (
            Transaction.objects.filter(
                account_id__in=ledger_ids,
                journal_entry__status=JournalEntry.STATUS_POSTED,
            )
            .values("account_id")
            .annotate(
                debit_total=Sum("debit"),
                credit_total=Sum("credit"),
            )
        )
        for row in rows:
            balances[row["account_id"]] = (
                (row["debit_total"] or ZERO)
                - (row["credit_total"] or ZERO)
            )

    bank_ids = [item.id for item in bank_accounts]
    latest_imports = {}
    for item in (
        BankStatementImport.objects.filter(bank_account_id__in=bank_ids)
        .select_related("bank_account")
        .order_by("bank_account_id", "-period_end", "-id")
    ):
        latest_imports.setdefault(item.bank_account_id, item)

    open_sessions = {}
    for item in (
        BankReconciliationSession.objects.filter(
            bank_account_id__in=bank_ids,
            status=BankReconciliationSession.STATUS_OPEN,
        )
        .select_related("bank_account")
        .order_by("bank_account_id", "-period_end", "-id")
    ):
        open_sessions.setdefault(item.bank_account_id, item)

    rows = []
    for bank in bank_accounts:
        rows.append(
            {
                "bank": bank,
                "book_balance": balances.get(bank.ledger_account_id, ZERO),
                "latest_import": latest_imports.get(bank.id),
                "open_reconciliation": open_sessions.get(bank.id),
            }
        )

    return {
        "book_cash": sum((balances[item] for item in ledger_ids), ZERO),
        "active_bank_count": len(bank_accounts),
        "bank_rows": rows,
        "banks_without_statement": sum(1 for row in rows if row["latest_import"] is None),
    }


def _ap_metrics(today) -> dict:
    open_qs = VendorBill.objects.filter(
        status__in=(VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL),
        posting_journal_entry__isnull=False,
    )
    overdue_qs = open_qs.filter(due_date__lt=today)
    due_next_7_qs = open_qs.filter(
        due_date__gte=today,
        due_date__lte=today + timedelta(days=7),
    )

    return {
        "outstanding": _outstanding_bill_total(open_qs),
        "overdue": _outstanding_bill_total(overdue_qs),
        "due_next_7": _outstanding_bill_total(due_next_7_qs),
        "open_count": open_qs.count(),
        "overdue_count": overdue_qs.count(),
        "draft_count": VendorBill.objects.filter(status=VendorBill.STATUS_DRAFT).count(),
    }


def _ar_metrics(today) -> dict:
    open_qs = CustomerInvoice.objects.filter(
        status__in=(CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL),
        posting_journal_entry__isnull=False,
    )
    overdue_qs = open_qs.filter(due_date__lt=today)
    due_next_7_qs = open_qs.filter(
        due_date__gte=today,
        due_date__lte=today + timedelta(days=7),
    )

    return {
        "outstanding": _outstanding_invoice_total(open_qs),
        "overdue": _outstanding_invoice_total(overdue_qs),
        "due_next_7": _outstanding_invoice_total(due_next_7_qs),
        "open_count": open_qs.count(),
        "overdue_count": overdue_qs.count(),
        "draft_count": CustomerInvoice.objects.filter(status=CustomerInvoice.STATUS_DRAFT).count(),
    }


def _payroll_metrics(today) -> dict:
    salary_qs = PayStub.objects.filter(
        pay_run__status__in=(PayRun.STATUS_POSTED, PayRun.STATUS_PAID),
        net_salary_payable__gt=ZERO,
    )
    remittance_qs = PayrollRemittance.objects.filter(
        status__in=(PayrollRemittance.STATUS_DRAFT, PayrollRemittance.STATUS_READY),
        journal_entry__isnull=True,
    )
    overdue_remittance_qs = remittance_qs.filter(due_date__lt=today)

    salary_due = _sum_field(salary_qs, "net_salary_payable")
    cra_due = _sum_field(remittance_qs, "total_due")

    return {
        "salary_due": salary_due,
        "salary_due_count": salary_qs.count(),
        "cra_due": cra_due,
        "total_due": salary_due + cra_due,
        "cra_due_count": remittance_qs.count(),
        "cra_overdue": _sum_field(overdue_remittance_qs, "total_due"),
        "cra_overdue_count": overdue_remittance_qs.count(),
        "calculated_runs": PayRun.objects.filter(status=PayRun.STATUS_CALCULATED).count(),
        "approved_runs": PayRun.objects.filter(status=PayRun.STATUS_APPROVED).count(),
        "missing_remittance": PayRun.objects.filter(
            status__in=(PayRun.STATUS_POSTED, PayRun.STATUS_PAID),
            total_remittance_due__gt=ZERO,
            remittance__isnull=True,
        ).count(),
    }


def _banking_metrics() -> dict:
    return {
        "pending_imports": BankStatementImport.objects.filter(
            status=BankStatementImport.STATUS_IMPORTED,
        ).count(),
        "unresolved_lines": BankStatementLine.objects.filter(
            match_status__in=(
                BankStatementLine.MATCH_UNMATCHED,
                BankStatementLine.MATCH_SUGGESTED,
            )
        ).count(),
        "open_reconciliations": BankReconciliationSession.objects.filter(
            status=BankReconciliationSession.STATUS_OPEN,
        ).count(),
    }


def _fund_metrics() -> dict:
    restricted_funds = Fund.objects.filter(
        is_active=True,
        status=Fund.STATUS_ACTIVE,
        is_restricted=True,
    )
    policy_issues = restricted_funds.exclude(
        policy__mode=FundPolicy.MODE_RESTRICTED,
        policy__enforce_rules=True,
    ).count()
    budget_setup_issues = restricted_funds.exclude(
        budgets__status=Budget.STATUS_ACTIVE,
        budgets__is_active=True,
    ).distinct().count()

    lines = list(
        BudgetLine.objects.filter(
            is_active=True,
            budget__is_active=True,
            budget__status=Budget.STATUS_ACTIVE,
            budget__fund__isnull=False,
            budget__fund__is_active=True,
            budget__fund__status=Fund.STATUS_ACTIVE,
        )
        .select_related("budget", "budget__fund")
        .order_by("budget__fund__code", "budget__code", "sort_order", "code")
    )
    line_metrics = build_budget_line_metrics(lines)

    watch_rows = []
    over_limit_count = 0
    near_limit_count = 0

    for line in lines:
        actual = line_metrics[line.id]["actual"]
        approved = line.approved_amount or ZERO

        if approved <= ZERO:
            if actual <= ZERO:
                continue
            ratio = None
            tone = "danger"
            over_limit_count += 1
        else:
            ratio = actual / approved
            if ratio > Decimal("1.00"):
                tone = "danger"
                over_limit_count += 1
            elif ratio >= BUDGET_WARNING_RATIO:
                tone = "warning"
                near_limit_count += 1
            else:
                continue

        watch_rows.append(
            {
                "line": line,
                "fund": line.budget.fund,
                "actual": actual,
                "approved": approved,
                "remaining": approved - actual,
                "used_percent": (ratio * Decimal("100")).quantize(Decimal("0.1")) if ratio is not None else None,
                "tone": tone,
            }
        )

    watch_rows.sort(
        key=lambda row: (
            0 if row["tone"] == "danger" else 1,
            -(row["used_percent"] or Decimal("9999")),
        )
    )

    return {
        "restricted_count": restricted_funds.count(),
        "policy_issues": policy_issues,
        "budget_setup_issues": budget_setup_issues,
        "near_limit_count": near_limit_count,
        "over_limit_count": over_limit_count,
        "watch_rows": watch_rows[:8],
    }


def _asset_metrics(current_period) -> dict:
    active_assets = FixedAsset.objects.filter(status=FixedAsset.STATUS_ACTIVE)
    due_count = 0

    if current_period:
        posted_for_period = FixedAssetDepreciation.objects.filter(
            asset_id=OuterRef("pk"),
            period_start=current_period.start_date,
            period_end=current_period.end_date,
        )
        due_count = (
            active_assets.filter(placed_in_service_date__lte=current_period.end_date)
            .annotate(has_period_depreciation=Exists(posted_for_period))
            .filter(has_period_depreciation=False)
            .count()
        )

    return {
        "active_count": active_assets.count(),
        "depreciation_due_count": due_count,
        "period": current_period,
        "period_is_open": bool(
            current_period and current_period.status == AccountingPeriod.STATUS_OPEN
        ),
    }


def build_operations_dashboard_metrics() -> dict:
    """Build operational accounting health from posted sub-ledger truth."""

    today = timezone.localdate()
    current_period = _current_month_period(today)

    cash = _cash_metrics()
    ap = _ap_metrics(today)
    ar = _ar_metrics(today)
    payroll = _payroll_metrics(today)
    banking = _banking_metrics()
    funds = _fund_metrics()
    assets = _asset_metrics(current_period)

    near_term_obligations = ap["outstanding"] + payroll["salary_due"] + payroll["cra_due"]
    near_term_resources = cash["book_cash"] + ar["outstanding"]

    return {
        "today": today,
        "current_period": current_period,
        "period_ready": bool(current_period and current_period.status == AccountingPeriod.STATUS_OPEN),
        "cash": cash,
        "ap": ap,
        "ar": ar,
        "payroll": payroll,
        "banking": banking,
        "funds": funds,
        "assets": assets,
        "draft_journals": JournalEntry.objects.filter(status=JournalEntry.STATUS_DRAFT).count(),
        "near_term_resources": near_term_resources,
        "near_term_obligations": near_term_obligations,
        "near_term_position": near_term_resources - near_term_obligations,
    }
