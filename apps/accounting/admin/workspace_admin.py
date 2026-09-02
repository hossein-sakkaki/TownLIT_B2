# apps/accounting/admin/workspace_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-02.
#

from urllib.parse import urlencode

from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import (
    AccountingPeriod,
    BankAccount,
    BankReconciliationSession,
    BankStatementImport,
    BankStatementLine,
    Budget,
    FounderLoan,
    Fund,
    FundPolicy,
    JournalEntry,
    PayPeriod,
    PayRun,
    PayrollCompensationPlan,
    PayrollEmployee,
    PayrollRemittance,
    PayrollYearConfig,
)

from apps.accounting.models.vendor_ap import VendorBill
from apps.accounting.models.customer_ar import CustomerInvoice
from apps.accounting.services.operations_dashboard_service import build_operations_dashboard_metrics
from .site import accounting_admin_site


def _admin_url(model_name: str, action: str = "changelist") -> str:
    return reverse(f"accounting_admin:accounting_{model_name}_{action}")


def _pay_run_remittance(pay_run):
    try:
        return pay_run.remittance
    except PayrollRemittance.DoesNotExist:
        return None


def _pay_run_action(pay_run: PayRun) -> dict:
    change_url = reverse(
        "accounting_admin:accounting_payrun_change",
        args=[pay_run.id],
    )

    if pay_run.status == PayRun.STATUS_CALCULATED:
        return {
            "label": "Approve",
            "url": reverse(
                "accounting_admin:accounting_payrun_approve",
                args=[pay_run.id],
            ),
            "tone": "warning",
        }

    if pay_run.status == PayRun.STATUS_APPROVED:
        return {
            "label": "Post to Ledger",
            "url": reverse(
                "accounting_admin:accounting_payrun_post",
                args=[pay_run.id],
            ),
            "tone": "primary",
        }

    if pay_run.status in {PayRun.STATUS_POSTED, PayRun.STATUS_PAID}:
        if pay_run.pay_stubs.filter(net_salary_payable__gt=0).exists():
            return {
                "label": "Record Salary Payment",
                "url": reverse(
                    "accounting_admin:accounting_payrun_record_salary_payment",
                    args=[pay_run.id],
                ),
                "tone": "primary",
            }

        remittance = _pay_run_remittance(pay_run)

        if pay_run.total_remittance_due > 0 and remittance is None:
            return {
                "label": "Create CRA Remittance",
                "url": reverse(
                    "accounting_admin:accounting_payrun_create_remittance",
                    args=[pay_run.id],
                ),
                "tone": "warning",
            }

        if remittance and remittance.status in {
            PayrollRemittance.STATUS_DRAFT,
            PayrollRemittance.STATUS_READY,
        } and not remittance.journal_entry_id:
            return {
                "label": "Record CRA Payment",
                "url": reverse(
                    "accounting_admin:accounting_payrollremittance_record_payment",
                    args=[remittance.id],
                ),
                "tone": "primary",
            }

    return {
        "label": "Open",
        "url": change_url,
        "tone": "neutral",
    }


def _payroll_queue(limit: int = 10) -> list[dict]:
    runs = (
        PayRun.objects.select_related("pay_period", "remittance")
        .filter(
            status__in=(
                PayRun.STATUS_CALCULATED,
                PayRun.STATUS_APPROVED,
                PayRun.STATUS_POSTED,
                PayRun.STATUS_PAID,
            )
        )
        .order_by("-run_date", "-id")[: max(limit * 2, 20)]
    )

    rows = []

    for pay_run in runs:
        action = _pay_run_action(pay_run)

        if action["label"] == "Open":
            continue

        rows.append(
            {
                "run_number": pay_run.run_number,
                "period": str(pay_run.pay_period),
                "status": pay_run.get_status_display(),
                "net_pay": pay_run.total_net_pay,
                "salary_payable": pay_run.total_salary_payable,
                "action": action,
                "change_url": reverse(
                    "accounting_admin:accounting_payrun_change",
                    args=[pay_run.id],
                ),
            }
        )

        if len(rows) >= limit:
            break

    return rows


def _remittance_queue(limit: int = 8) -> list[dict]:
    remittances = (
        PayrollRemittance.objects.select_related("pay_run", "pay_run__pay_period")
        .filter(
            status__in=(
                PayrollRemittance.STATUS_DRAFT,
                PayrollRemittance.STATUS_READY,
            ),
            journal_entry__isnull=True,
        )
        .order_by("due_date", "id")[:limit]
    )

    return [
        {
            "id": item.id,
            "run_number": item.pay_run.run_number,
            "due_date": item.due_date,
            "total_due": item.total_due,
            "change_url": reverse(
                "accounting_admin:accounting_payrun_change",
                args=[item.pay_run_id],
            ),
            "pay_url": reverse(
                "accounting_admin:accounting_payrollremittance_record_payment",
                args=[item.id],
            ),
        }
        for item in remittances
    ]


def _employee_setup_rows(pay_period, limit: int = 12) -> list[dict]:
    employees = (
        PayrollEmployee.objects.filter(is_active=True)
        .prefetch_related("compensation_plans")
        .order_by("display_name")[:limit]
    )

    rows = []

    for employee in employees:
        plans = sorted(
            [
                plan
                for plan in employee.compensation_plans.all()
                if plan.status == PayrollCompensationPlan.STATUS_ACTIVE
            ],
            key=lambda item: (item.effective_from, item.id),
            reverse=True,
        )
        plan = plans[0] if plans else None

        if plan and plan.pay_type == PayrollCompensationPlan.PAY_TYPE_HOURLY:
            pay_label = f"Hourly — ${plan.hourly_rate}/hr"
        elif plan:
            pay_label = f"Monthly — ${plan.monthly_salary}/month"
        else:
            pay_label = "Payroll setup required"

        create_url = reverse("accounting_admin:accounting-create-pay-run")
        params = [f"employee={employee.id}"]
        if pay_period:
            params.append(f"pay_period={pay_period.id}")

        rows.append(
            {
                "employee": employee,
                "plan": plan,
                "pay_label": pay_label,
                "ready": bool(plan),
                "change_url": reverse(
                    "accounting_admin:accounting_payrollemployee_change",
                    args=[employee.id],
                ),
                "create_url": f"{create_url}?{'&'.join(params)}" if plan else "",
            }
        )

    return rows



def _reconciliation_review_url(session: BankReconciliationSession) -> str:
    return reverse(
        "accounting_admin:accounting_bankreconciliationsession_review",
        args=[session.id],
    )


def _statement_import_url(bank_account: BankAccount | None = None) -> str:
    url = _admin_url("bankstatementimport", "add")
    if not bank_account:
        return url
    return f"{url}?{urlencode({'bank_account': bank_account.id})}"


def _start_reconciliation_url(statement: BankStatementImport) -> str:
    params = {
        "bank_account": statement.bank_account_id,
        "period_start": statement.period_start.isoformat() if statement.period_start else "",
        "period_end": statement.period_end.isoformat() if statement.period_end else "",
    }

    if statement.closing_balance is not None:
        params["statement_ending_balance"] = statement.closing_balance

    params = {key: value for key, value in params.items() if value != ""}
    return f'{_admin_url("bankreconciliationsession", "add")}?{urlencode(params)}'


def _bank_account_rows(selected_bank_id: int | None = None) -> list[dict]:
    accounts = (
        BankAccount.objects.filter(
            status=BankAccount.STATUS_ACTIVE,
            is_active=True,
        )
        .select_related("institution", "ledger_account")
        .order_by("-is_primary", "code")
    )

    rows = []

    for account in accounts:
        unresolved_count = BankStatementLine.objects.filter(
            bank_account=account,
            match_status__in=(
                BankStatementLine.MATCH_UNMATCHED,
                BankStatementLine.MATCH_SUGGESTED,
            ),
        ).count()

        latest_import = (
            BankStatementImport.objects.filter(bank_account=account)
            .order_by("-period_end", "-id")
            .first()
        )
        open_session = (
            BankReconciliationSession.objects.filter(
                bank_account=account,
                status=BankReconciliationSession.STATUS_OPEN,
            )
            .order_by("-period_end", "-id")
            .first()
        )
        latest_session = (
            BankReconciliationSession.objects.filter(bank_account=account)
            .order_by("-period_end", "-id")
            .first()
        )
        session_for_latest_import = None
        if latest_import and latest_import.period_start and latest_import.period_end:
            session_for_latest_import = (
                BankReconciliationSession.objects.filter(
                    bank_account=account,
                    period_start=latest_import.period_start,
                    period_end=latest_import.period_end,
                )
                .order_by("-id")
                .first()
            )

        if open_session:
            action = {
                "label": "Continue reconciliation",
                "url": _reconciliation_review_url(open_session),
                "tone": "primary",
            }
        elif session_for_latest_import:
            action = {
                "label": "Review reconciliation",
                "url": _reconciliation_review_url(session_for_latest_import),
                "tone": "neutral",
            }
        elif latest_import and latest_import.status == BankStatementImport.STATUS_PROCESSED:
            action = {
                "label": "Start reconciliation",
                "url": _start_reconciliation_url(latest_import),
                "tone": "warning",
            }
        else:
            action = {
                "label": "Import statement",
                "url": _statement_import_url(account),
                "tone": "neutral",
            }

        rows.append(
            {
                "account": account,
                "selected": bool(selected_bank_id and account.id == selected_bank_id),
                "unresolved_count": unresolved_count,
                "latest_import": latest_import,
                "open_session": open_session,
                "latest_session": latest_session,
                "action": action,
                "workspace_url": (
                    f'{reverse("accounting_admin:accounting-banking-workspace")}'
                    f'?bank_account={account.id}'
                ),
            }
        )

    return rows


def build_banking_workspace_context(request) -> dict:
    selected_bank_id = None
    raw_bank_id = request.GET.get("bank_account")

    if raw_bank_id and raw_bank_id.isdigit():
        selected_bank_id = int(raw_bank_id)

    bank_rows = _bank_account_rows(selected_bank_id)
    selected_bank = next(
        (row["account"] for row in bank_rows if row["selected"]),
        None,
    )

    imports = BankStatementImport.objects.select_related("bank_account", "imported_by")
    sessions = BankReconciliationSession.objects.select_related(
        "bank_account",
        "completed_by",
        "locked_by",
    )
    lines = BankStatementLine.objects.select_related(
        "bank_account",
        "statement_import",
        "matched_journal_entry",
    ).filter(
        match_status__in=(
            BankStatementLine.MATCH_UNMATCHED,
            BankStatementLine.MATCH_SUGGESTED,
        )
    )

    if selected_bank:
        imports = imports.filter(bank_account=selected_bank)
        sessions = sessions.filter(bank_account=selected_bank)
        lines = lines.filter(bank_account=selected_bank)

    recent_imports = list(imports.order_by("-period_end", "-id")[:10])
    recent_sessions = list(sessions.order_by("-period_end", "-id")[:10])
    unresolved_lines = list(lines.order_by("-transaction_date", "-id")[:15])

    import_rows = []
    for statement in recent_imports:
        existing_session = None
        if statement.period_start and statement.period_end:
            existing_session = (
                BankReconciliationSession.objects.filter(
                    bank_account=statement.bank_account,
                    period_start=statement.period_start,
                    period_end=statement.period_end,
                )
                .order_by("-id")
                .first()
            )

        import_rows.append(
            {
                "statement": statement,
                "line_count": statement.lines.count(),
                "unresolved_count": statement.lines.filter(
                    match_status__in=(
                        BankStatementLine.MATCH_UNMATCHED,
                        BankStatementLine.MATCH_SUGGESTED,
                    )
                ).count(),
                "change_url": reverse(
                    "accounting_admin:accounting_bankstatementimport_change",
                    args=[statement.id],
                ),
                "review_url": (
                    _reconciliation_review_url(existing_session)
                    if existing_session
                    else ""
                ),
                "start_url": (
                    _start_reconciliation_url(statement)
                    if not existing_session
                    and statement.status == BankStatementImport.STATUS_PROCESSED
                    else ""
                ),
            }
        )

    session_rows = [
        {
            "session": session,
            "review_url": _reconciliation_review_url(session),
            "change_url": reverse(
                "accounting_admin:accounting_bankreconciliationsession_change",
                args=[session.id],
            ),
        }
        for session in recent_sessions
    ]

    line_rows = [
        {
            "line": line,
            "change_url": reverse(
                "accounting_admin:accounting_bankstatementline_change",
                args=[line.id],
            ),
        }
        for line in unresolved_lines
    ]

    pending_import_count = imports.filter(
        status=BankStatementImport.STATUS_IMPORTED,
    ).count()
    open_session_count = sessions.filter(
        status=BankReconciliationSession.STATUS_OPEN,
    ).count()
    unresolved_count = lines.count()

    return {
        "banking_selected_bank": selected_bank,
        "banking_bank_rows": bank_rows,
        "banking_import_rows": import_rows,
        "banking_session_rows": session_rows,
        "banking_line_rows": line_rows,
        "banking_counts": {
            "active_accounts": len(bank_rows),
            "pending_imports": pending_import_count,
            "open_sessions": open_session_count,
            "unresolved_lines": unresolved_count,
        },
        "banking_urls": {
            "home": reverse("accounting_admin:index"),
            "workspace": reverse("accounting_admin:accounting-banking-workspace"),
            "import_statement": _statement_import_url(selected_bank),
            "statement_imports": _admin_url("bankstatementimport"),
            "bank_lines": _admin_url("bankstatementline"),
            "reconciliations": _admin_url("bankreconciliationsession"),
            "bank_accounts": _admin_url("bankaccount"),
            "add_bank_account": _admin_url("bankaccount", "add"),
        },
    }

def build_accounting_workspace_context(*, include_operations: bool = False) -> dict:
    today = timezone.localdate()

    current_period = (
        AccountingPeriod.objects.filter(
            period_type=AccountingPeriod.PERIOD_TYPE_MONTH,
            start_date__lte=today,
            end_date__gte=today,
        )
        .order_by("start_date", "id")
        .first()
    )

    active_bank_exists = BankAccount.objects.filter(
        status=BankAccount.STATUS_ACTIVE,
        is_active=True,
    ).exists()

    next_pay_period = (
        PayPeriod.objects.filter(
            status__in=(PayPeriod.STATUS_OPEN, PayPeriod.STATUS_PROCESSING),
        )
        .select_related("schedule")
        .order_by("pay_date", "start_date", "id")
        .first()
    )

    payroll_year_ready = bool(
        next_pay_period
        and PayrollYearConfig.objects.filter(
            year=next_pay_period.tax_year,
            is_active=True,
        ).exists()
    )

    active_plan_exists = PayrollCompensationPlan.objects.filter(
        employee_id=OuterRef("pk"),
        status=PayrollCompensationPlan.STATUS_ACTIVE,
    )
    employee_base = PayrollEmployee.objects.filter(is_active=True).annotate(
        has_active_plan=Exists(active_plan_exists),
    )
    active_employee_count = employee_base.count()
    ready_employee_count = employee_base.filter(has_active_plan=True).count()
    setup_issue_count = active_employee_count - ready_employee_count

    payroll_calculated = PayRun.objects.filter(status=PayRun.STATUS_CALCULATED).count()
    payroll_approved = PayRun.objects.filter(status=PayRun.STATUS_APPROVED).count()
    payroll_salary_due = (
        PayRun.objects.filter(
            status__in=(PayRun.STATUS_POSTED, PayRun.STATUS_PAID),
            pay_stubs__net_salary_payable__gt=0,
        )
        .distinct()
        .count()
    )
    payroll_remittance_due = PayrollRemittance.objects.filter(
        status__in=(PayrollRemittance.STATUS_DRAFT, PayrollRemittance.STATUS_READY),
        journal_entry__isnull=True,
    ).count()
    payroll_missing_remittance = (
        PayRun.objects.filter(
            status__in=(PayRun.STATUS_POSTED, PayRun.STATUS_PAID),
            total_remittance_due__gt=0,
            remittance__isnull=True,
        ).count()
    )

    pending_imports = BankStatementImport.objects.filter(
        status=BankStatementImport.STATUS_IMPORTED,
    ).count()
    unmatched_bank_lines = BankStatementLine.objects.filter(
        match_status__in=(
            BankStatementLine.MATCH_UNMATCHED,
            BankStatementLine.MATCH_SUGGESTED,
        )
    ).count()
    open_reconciliations = BankReconciliationSession.objects.filter(
        status=BankReconciliationSession.STATUS_OPEN,
    ).count()

    draft_journals = JournalEntry.objects.filter(status=JournalEntry.STATUS_DRAFT).count()
    open_founder_loans = FounderLoan.objects.filter(
        status__in=(FounderLoan.STATUS_OPEN, FounderLoan.STATUS_PARTIAL),
    ).count()

    restricted_funds = Fund.objects.filter(
        is_active=True,
        status=Fund.STATUS_ACTIVE,
        is_restricted=True,
    )
    restricted_policy_issues = restricted_funds.exclude(
        policy__mode=FundPolicy.MODE_RESTRICTED,
        policy__enforce_rules=True,
    ).count()
    restricted_budget_issues = restricted_funds.exclude(
        budgets__status=Budget.STATUS_ACTIVE,
        budgets__is_active=True,
    ).distinct().count()
    fund_attention = restricted_policy_issues + restricted_budget_issues

    ap_overdue = VendorBill.objects.filter(
        status__in=(VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL),
        due_date__lt=today,
        posting_journal_entry__isnull=False,
    ).count()
    ap_drafts = VendorBill.objects.filter(status=VendorBill.STATUS_DRAFT).count()
    ap_attention = ap_overdue + ap_drafts

    ar_overdue = CustomerInvoice.objects.filter(
        status__in=(CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL),
        due_date__lt=today,
        posting_journal_entry__isnull=False,
    ).count()
    ar_drafts = CustomerInvoice.objects.filter(status=CustomerInvoice.STATUS_DRAFT).count()
    ar_attention = ar_overdue + ar_drafts

    payroll_attention = (
        payroll_calculated
        + payroll_approved
        + payroll_salary_due
        + payroll_remittance_due
        + payroll_missing_remittance
    )
    banking_attention = pending_imports + unmatched_bank_lines + open_reconciliations

    context = {
        "workspace_today": today,
        "workspace_current_period": current_period,
        "workspace_period_ready": bool(
            current_period and current_period.status == AccountingPeriod.STATUS_OPEN
        ),
        "workspace_bank_ready": active_bank_exists,
        "workspace_next_pay_period": next_pay_period,
        "workspace_payroll_year_ready": payroll_year_ready,
        "workspace_payroll_setup_issues": setup_issue_count,
        "workspace_attention_total": payroll_attention + banking_attention + fund_attention + ap_attention + ar_attention + draft_journals,
        "workspace_counts": {
            "payroll_attention": payroll_attention,
            "payroll_calculated": payroll_calculated,
            "payroll_approved": payroll_approved,
            "payroll_salary_due": payroll_salary_due,
            "payroll_remittance_due": payroll_remittance_due,
            "payroll_missing_remittance": payroll_missing_remittance,
            "active_employees": active_employee_count,
            "ready_employees": ready_employee_count,
            "payroll_setup_issues": setup_issue_count,
            "banking_attention": banking_attention,
            "pending_imports": pending_imports,
            "unmatched_bank_lines": unmatched_bank_lines,
            "open_reconciliations": open_reconciliations,
            "draft_journals": draft_journals,
            "open_founder_loans": open_founder_loans,
            "ap_attention": ap_attention,
            "ap_overdue": ap_overdue,
            "ap_drafts": ap_drafts,
            "ar_attention": ar_attention,
            "ar_overdue": ar_overdue,
            "ar_drafts": ar_drafts,
            "fund_attention": fund_attention,
            "restricted_policy_issues": restricted_policy_issues,
            "restricted_budget_issues": restricted_budget_issues,
        },
        "workspace_payroll_queue": _payroll_queue(),
        "workspace_remittance_queue": _remittance_queue(),
        "workspace_employee_rows": _employee_setup_rows(next_pay_period),
        "workspace_urls": {
            "dashboard": reverse("accounting_admin:accounting-dashboard-admin"),
            "reports": reverse("accounting_admin:accounting-report-hub"),
            "payroll_workspace": reverse("accounting_admin:accounting-payroll-workspace"),
            "banking_workspace": reverse("accounting_admin:accounting-banking-workspace"),
            "money_workspace": reverse("accounting_admin:accounting-money-workspace"),
            "asset_workspace": reverse("accounting_admin:accounting-asset-workspace"),
            "create_payroll": reverse("accounting_admin:accounting-create-pay-run"),
            "create_vacation_pay": reverse("accounting_admin:accounting-create-vacation-pay-run"),
            "pay_runs": _admin_url("payrun"),
            "employees": _admin_url("payrollemployee"),
            "add_employee": _admin_url("payrollemployee", "add"),
            "compensation_plans": _admin_url("payrollcompensationplan"),
            "pay_periods": _admin_url("payperiod"),
            "payroll_year_configs": _admin_url("payrollyearconfig"),
            "remittances": _admin_url("payrollremittance"),
            "bank_accounts": _admin_url("bankaccount"),
            "add_bank_account": _admin_url("bankaccount", "add"),
            "import_statement": _admin_url("bankstatementimport", "add"),
            "statement_imports": _admin_url("bankstatementimport"),
            "bank_lines": _admin_url("bankstatementline"),
            "unmatched_bank_lines": (
                f'{_admin_url("bankstatementline")}?match_status__exact='
                f"{BankStatementLine.MATCH_UNMATCHED}"
            ),
            "reconciliations": _admin_url("bankreconciliationsession"),
            "manual_journal": _admin_url("journalentry", "add"),
            "journals": _admin_url("journalentry"),
            "draft_journals": (
                f'{_admin_url("journalentry")}?status__exact={JournalEntry.STATUS_DRAFT}'
            ),
            "founder_loans": _admin_url("founderloan"),
            "periods": _admin_url("accountingperiod"),
            "generate_periods": reverse("accounting_admin:accounting-generate-periods"),
            "ap_workspace": reverse("accounting_admin:accounting-ap-workspace"),
            "add_vendor_bill": _admin_url("vendorbill", "add"),
            "vendors": _admin_url("vendor"),
            "ar_workspace": reverse("accounting_admin:accounting-ar-workspace"),
            "add_customer_invoice": _admin_url("customerinvoice", "add"),
            "customers": _admin_url("customer"),
            "funds": reverse("accounting_admin:accounting-funds-workspace"),
            "raw_funds": _admin_url("fund"),
            "accounts": _admin_url("account"),
            "recurring": _admin_url("recurringjournaltemplate"),
        },
    }

    if include_operations:
        operations = build_operations_dashboard_metrics()
        context["workspace_operations"] = operations
        context["workspace_actions"] = _build_operations_actions(operations)

    return context


def _build_operations_actions(operations: dict) -> list[dict]:
    actions = []

    def add(*, tone, title, detail, url, label):
        actions.append({
            "tone": tone,
            "title": title,
            "detail": detail,
            "url": url,
            "label": label,
        })

    if not operations["period_ready"]:
        period = operations.get("current_period")
        detail = (
            f"Current monthly period {period.code} is {period.get_status_display()}."
            if period
            else "No monthly accounting period covers today."
        )
        add(
            tone="danger",
            title="Posting period requires attention",
            detail=detail,
            url=_admin_url("accountingperiod"),
            label="Review periods",
        )

    if operations["cash"]["active_bank_count"] == 0:
        add(
            tone="danger",
            title="No active bank account",
            detail="Bank-backed workflows and reconciliation require an active bank account.",
            url=_admin_url("bankaccount", "add"),
            label="Set up bank",
        )

    if operations["ap"]["overdue_count"]:
        add(
            tone="danger",
            title=f'{operations["ap"]["overdue_count"]} overdue vendor bill(s)',
            detail=f'Outstanding overdue AP: ${operations["ap"]["overdue"]:,.2f}.',
            url=reverse("accounting_admin:accounting-ap-workspace"),
            label="Review AP",
        )

    if operations["ar"]["overdue_count"]:
        add(
            tone="warning",
            title=f'{operations["ar"]["overdue_count"]} overdue customer invoice(s)',
            detail=f'Outstanding overdue AR: ${operations["ar"]["overdue"]:,.2f}.',
            url=reverse("accounting_admin:accounting-ar-workspace"),
            label="Review AR",
        )

    if operations["payroll"]["salary_due_count"]:
        add(
            tone="danger",
            title="Salary payments outstanding",
            detail=f'Unpaid salary balance: ${operations["payroll"]["salary_due"]:,.2f}.',
            url=reverse("accounting_admin:accounting-payroll-workspace"),
            label="Open payroll",
        )

    if operations["payroll"]["cra_overdue_count"]:
        add(
            tone="danger",
            title="CRA remittance overdue",
            detail=f'Overdue CRA balance: ${operations["payroll"]["cra_overdue"]:,.2f}.',
            url=reverse("accounting_admin:accounting-payroll-workspace"),
            label="Review CRA",
        )
    elif operations["payroll"]["cra_due_count"]:
        add(
            tone="warning",
            title="CRA remittance pending",
            detail=f'CRA payable waiting for payment: ${operations["payroll"]["cra_due"]:,.2f}.',
            url=reverse("accounting_admin:accounting-payroll-workspace"),
            label="Review CRA",
        )

    if operations["payroll"]["calculated_runs"] or operations["payroll"]["approved_runs"]:
        add(
            tone="warning",
            title="Payroll run waiting for workflow",
            detail=(
                f'{operations["payroll"]["calculated_runs"]} calculated and '
                f'{operations["payroll"]["approved_runs"]} approved run(s) still need action.'
            ),
            url=reverse("accounting_admin:accounting-payroll-workspace"),
            label="Continue payroll",
        )

    if operations["payroll"]["missing_remittance"]:
        add(
            tone="warning",
            title="Payroll remittance record missing",
            detail=f'{operations["payroll"]["missing_remittance"]} posted pay run(s) still need a CRA remittance record.',
            url=reverse("accounting_admin:accounting-payroll-workspace"),
            label="Create remittance",
        )

    if operations["banking"]["unresolved_lines"]:
        add(
            tone="warning",
            title="Bank transactions need review",
            detail=f'{operations["banking"]["unresolved_lines"]} imported line(s) remain unmatched or suggested.',
            url=reverse("accounting_admin:accounting-banking-workspace"),
            label="Reconcile bank",
        )

    if operations["banking"]["pending_imports"]:
        add(
            tone="warning",
            title="Bank statement import pending",
            detail=f'{operations["banking"]["pending_imports"]} statement import(s) are not fully processed.',
            url=_admin_url("bankstatementimport"),
            label="Review imports",
        )

    if operations["assets"]["depreciation_due_count"]:
        tone = "warning" if operations["assets"]["period_is_open"] else "danger"
        add(
            tone=tone,
            title="Depreciation pending",
            detail=f'{operations["assets"]["depreciation_due_count"]} active asset(s) have no depreciation entry for the current month.',
            url=reverse("accounting_admin:accounting-asset-workspace"),
            label="Review assets",
        )

    fund_attention = (
        operations["funds"]["policy_issues"]
        + operations["funds"]["budget_setup_issues"]
        + operations["funds"]["near_limit_count"]
        + operations["funds"]["over_limit_count"]
    )
    if fund_attention:
        tone = "danger" if operations["funds"]["over_limit_count"] else "warning"
        add(
            tone=tone,
            title="Fund or budget attention required",
            detail=(
                f'{operations["funds"]["over_limit_count"]} over limit, '
                f'{operations["funds"]["near_limit_count"]} near limit, '
                f'{operations["funds"]["policy_issues"] + operations["funds"]["budget_setup_issues"]} setup issue(s).'
            ),
            url=reverse("accounting_admin:accounting-funds-workspace"),
            label="Review funds",
        )

    if operations["draft_journals"]:
        add(
            tone="neutral",
            title="Draft journals waiting",
            detail=f'{operations["draft_journals"]} manual journal(s) remain in draft.',
            url=f'{_admin_url("journalentry")}?status__exact={JournalEntry.STATUS_DRAFT}',
            label="Review journals",
        )

    tone_rank = {"danger": 0, "warning": 1, "neutral": 2}
    actions.sort(key=lambda item: tone_rank.get(item["tone"], 9))
    return actions


def payroll_workspace_view(request):
    context = {
        **accounting_admin_site.each_context(request),
        **build_accounting_workspace_context(),
        "title": "Payroll Workspace",
    }

    return render(
        request,
        "admin/accounting/payroll/workspace.html",
        context,
    )



def banking_workspace_view(request):
    context = {
        **accounting_admin_site.each_context(request),
        **build_banking_workspace_context(request),
        "title": "Banking & Reconciliation",
    }

    return render(
        request,
        "admin/accounting/banking/workspace.html",
        context,
    )
