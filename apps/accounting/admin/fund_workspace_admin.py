# apps/accounting/admin/fund_workspace_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounting.models import (
    Account,
    Budget,
    BudgetLine,
    Fund,
    FundAllowedAccount,
    FundAllowedBudgetLine,
    FundPolicy,
    JournalEntry,
    Transaction,
)
from apps.accounting.services.fund_monitoring_service import (
    build_budget_line_metrics,
    build_fund_metrics,
)

from .site import accounting_admin_site


ZERO = Decimal("0.00")


def _admin_url(model_name: str, action: str = "changelist") -> str:
    return reverse(f"accounting_admin:accounting_{model_name}_{action}")


def _with_query(url: str, **params) -> str:
    cleaned = {key: value for key, value in params.items() if value not in (None, "")}
    return f"{url}?{urlencode(cleaned)}" if cleaned else url


def _fund_detail_url(fund: Fund) -> str:
    return reverse("accounting_admin:accounting-fund-detail", args=[fund.id])


def _fund_config_url(fund: Fund) -> str:
    return reverse("accounting_admin:accounting-fund-configure", args=[fund.id])


def _fund_report_url(route_name: str, fund: Fund, file_format: str = "xlsx") -> str:
    return _with_query(
        reverse(route_name, kwargs={"fund_code": fund.code}),
        file_format=file_format,
    )


def _fund_attention(fund: Fund, *, has_budget: bool) -> list[str]:
    issues = []
    policy = getattr(fund, "policy", None)

    if fund.is_restricted:
        if not policy or policy.mode != FundPolicy.MODE_RESTRICTED:
            issues.append("Restriction policy needs review")
        elif not policy.enforce_rules:
            issues.append("Restriction enforcement is disabled")

        if not has_budget:
            issues.append("No active budget")

    if fund.status != Fund.STATUS_ACTIVE or not fund.is_active:
        issues.append("Fund is not open for posting")

    return issues


def _budget_rows(fund: Fund) -> list[dict]:
    budgets = list(
        Budget.objects.filter(fund=fund)
        .prefetch_related("lines")
        .order_by("-start_date", "code")
    )
    lines = [line for budget in budgets for line in budget.lines.all()]
    line_metrics = build_budget_line_metrics(lines)

    rows = []
    for budget in budgets:
        budget_lines = []
        total_approved = ZERO
        total_actual = ZERO

        for line in sorted(budget.lines.all(), key=lambda item: (item.sort_order, item.code)):
            metrics = line_metrics.get(line.id, {"operating_spend": ZERO, "capital_spend": ZERO, "actual": ZERO})
            approved = line.approved_amount or ZERO
            actual = metrics["actual"]
            remaining = approved - actual
            used_percent = (actual / approved * Decimal("100.00")) if approved > ZERO else ZERO

            budget_lines.append(
                {
                    "line": line,
                    "approved": approved,
                    "operating_spend": metrics["operating_spend"],
                    "capital_spend": metrics["capital_spend"],
                    "actual": actual,
                    "remaining": remaining,
                    "used_percent": used_percent.quantize(Decimal("0.1")),
                    "warning": approved > ZERO and used_percent >= Decimal("80.00"),
                    "over": remaining < ZERO,
                    "change_url": reverse(
                        "accounting_admin:accounting_budgetline_change",
                        args=[line.id],
                    ),
                }
            )
            total_approved += approved
            total_actual += actual

        rows.append(
            {
                "budget": budget,
                "lines": budget_lines,
                "total_approved": total_approved,
                "total_actual": total_actual,
                "remaining": total_approved - total_actual,
                "change_url": reverse(
                    "accounting_admin:accounting_budget_change",
                    args=[budget.id],
                ),
            }
        )

    return rows


def _recent_fund_activity(fund: Fund, limit: int = 20) -> list[dict]:
    rows = (
        Transaction.objects.filter(
            fund=fund,
            journal_entry__status=JournalEntry.STATUS_POSTED,
        )
        .select_related("journal_entry", "account", "budget_line")
        .order_by("-journal_entry__entry_date", "-journal_entry_id", "line_number")[:limit]
    )

    result = []
    for tx in rows:
        if tx.account.account_type == Account.TYPE_REVENUE:
            effect = (tx.credit or ZERO) - (tx.debit or ZERO)
            kind = "Income"
        elif tx.account.account_type == Account.TYPE_EXPENSE:
            effect = -((tx.debit or ZERO) - (tx.credit or ZERO))
            kind = "Expense"
        elif tx.account.account_type == Account.TYPE_ASSET and tx.account.parent_id and tx.account.parent.code == "1500":
            effect = -((tx.debit or ZERO) - (tx.credit or ZERO))
            kind = "Capital asset"
        else:
            continue

        result.append(
            {
                "tx": tx,
                "kind": kind,
                "effect": effect,
                "journal_url": reverse(
                    "accounting_admin:accounting_journalentry_change",
                    args=[tx.journal_entry_id],
                ),
            }
        )

    return result


class FundRestrictionForm(forms.Form):
    legally_restricted = forms.BooleanField(
        required=False,
        label="Legally / contractually restricted",
    )
    mode = forms.ChoiceField(choices=FundPolicy.MODE_CHOICES, label="Posting policy")
    enforce_rules = forms.BooleanField(required=False, initial=True)
    enforce_date_window = forms.BooleanField(required=False, initial=True)
    prevent_budget_overrun = forms.BooleanField(required=False, initial=True)
    require_budget_line_for_expenses = forms.BooleanField(required=False, initial=True)
    allowed_revenue_accounts = forms.ModelMultipleChoiceField(
        queryset=Account.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Allowed revenue accounts",
    )
    allowed_expense_accounts = forms.ModelMultipleChoiceField(
        queryset=Account.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Allowed expense accounts",
    )
    allowed_asset_accounts = forms.ModelMultipleChoiceField(
        queryset=Account.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Allowed capital asset accounts",
        help_text="Use for equipment purchases that belong to this fund.",
    )
    allowed_budget_lines = forms.ModelMultipleChoiceField(
        queryset=BudgetLine.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Allowed budget lines",
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, fund: Fund, **kwargs):
        super().__init__(*args, **kwargs)
        self.fund = fund
        self.fields["allowed_revenue_accounts"].queryset = Account.objects.filter(
            account_type=Account.TYPE_REVENUE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")
        self.fields["allowed_expense_accounts"].queryset = Account.objects.filter(
            account_type=Account.TYPE_EXPENSE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")
        self.fields["allowed_asset_accounts"].queryset = Account.objects.filter(
            account_type=Account.TYPE_ASSET,
            parent__code="1500",
            is_active=True,
            allows_posting=True,
        ).order_by("code")
        self.fields["allowed_budget_lines"].queryset = BudgetLine.objects.filter(
            budget__fund=fund,
            budget__is_active=True,
            is_active=True,
        ).select_related("budget").order_by("budget__code", "sort_order", "code")

        if self.is_bound:
            return

        policy = getattr(fund, "policy", None)
        allowed = list(fund.allowed_accounts.select_related("account"))
        self.initial.update(
            {
                "legally_restricted": fund.is_restricted,
                "mode": policy.mode if policy else (FundPolicy.MODE_RESTRICTED if fund.is_restricted else FundPolicy.MODE_OPEN),
                "enforce_rules": policy.enforce_rules if policy else True,
                "enforce_date_window": policy.enforce_date_window if policy else True,
                "prevent_budget_overrun": policy.prevent_budget_overrun if policy else True,
                "require_budget_line_for_expenses": policy.require_budget_line_for_expenses if policy else fund.is_restricted,
                "allowed_revenue_accounts": [item.account_id for item in allowed if item.allow_revenue],
                "allowed_expense_accounts": [item.account_id for item in allowed if item.allow_expense],
                "allowed_asset_accounts": [item.account_id for item in allowed if item.allow_asset],
                "allowed_budget_lines": list(fund.allowed_budget_lines.values_list("budget_line_id", flat=True)),
                "note": policy.note if policy else "",
            }
        )

    def clean(self):
        data = super().clean()
        mode = data.get("mode")
        if mode == FundPolicy.MODE_RESTRICTED and data.get("enforce_rules"):
            if not (
                data.get("allowed_revenue_accounts")
                or data.get("allowed_expense_accounts")
                or data.get("allowed_asset_accounts")
            ):
                raise forms.ValidationError(
                    "A restricted enforced fund must allow at least one posting account."
                )
        return data

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        self.fund.is_restricted = data["legally_restricted"]
        self.fund.save(update_fields=["is_restricted", "updated_at"])

        policy, _ = FundPolicy.objects.update_or_create(
            fund=self.fund,
            defaults={
                "mode": data["mode"],
                "enforce_rules": data["enforce_rules"],
                "enforce_date_window": data["enforce_date_window"],
                "prevent_budget_overrun": data["prevent_budget_overrun"],
                "require_budget_line_for_expenses": data["require_budget_line_for_expenses"],
                "note": data.get("note", ""),
            },
        )

        FundAllowedAccount.objects.filter(fund=self.fund).delete()
        selected_groups = (
            (data["allowed_revenue_accounts"], Account.TYPE_REVENUE),
            (data["allowed_expense_accounts"], Account.TYPE_EXPENSE),
            (data["allowed_asset_accounts"], Account.TYPE_ASSET),
        )

        for accounts, account_type in selected_groups:
            for account in accounts:
                FundAllowedAccount.objects.create(
                    fund=self.fund,
                    account=account,
                    allow_revenue=account_type == Account.TYPE_REVENUE,
                    allow_expense=account_type == Account.TYPE_EXPENSE,
                    allow_asset=account_type == Account.TYPE_ASSET,
                    allow_liability=False,
                    allow_equity=False,
                )

        FundAllowedBudgetLine.objects.filter(fund=self.fund).delete()
        FundAllowedBudgetLine.objects.bulk_create(
            [
                FundAllowedBudgetLine(fund=self.fund, budget_line=line)
                for line in data["allowed_budget_lines"]
            ]
        )
        return policy


def funds_workspace_view(request):
    show_all = request.GET.get("all") == "1"
    funds_qs = Fund.objects.select_related("policy").order_by("code")
    if not show_all:
        funds_qs = funds_qs.filter(is_active=True)
    funds = list(funds_qs)

    metrics = build_fund_metrics(funds)
    active_budget_fund_ids = set(
        Budget.objects.filter(
            fund_id__in=[fund.id for fund in funds],
            status=Budget.STATUS_ACTIVE,
            is_active=True,
        ).values_list("fund_id", flat=True)
    )

    rows = []
    attention_count = 0
    for fund in funds:
        item_metrics = metrics.get(fund.id, {})
        issues = _fund_attention(fund, has_budget=fund.id in active_budget_fund_ids)
        attention_count += len(issues)
        rows.append(
            {
                "fund": fund,
                "metrics": item_metrics,
                "issues": issues,
                "detail_url": _fund_detail_url(fund),
                "income_url": _with_query(reverse("accounting_admin:accounting-record-income"), fund=fund.id),
                "expense_url": _with_query(reverse("accounting_admin:accounting-record-expense"), fund=fund.id),
            }
        )

    context = {
        **accounting_admin_site.each_context(request),
        "title": "Funds & Budgets",
        "fund_rows": rows,
        "fund_attention_count": attention_count,
        "show_all": show_all,
        "add_fund_url": _admin_url("fund", "add"),
        "budgets_url": _admin_url("budget"),
        "home_url": reverse("accounting_admin:index"),
    }
    return render(request, "admin/accounting/funds/workspace.html", context)


def fund_detail_view(request, fund_id: int):
    fund = get_object_or_404(Fund.objects.select_related("policy"), pk=fund_id)
    metrics = build_fund_metrics([fund])[fund.id]
    budgets = _budget_rows(fund)
    has_active_budget = any(
        row["budget"].status == Budget.STATUS_ACTIVE and row["budget"].is_active
        for row in budgets
    )
    issues = _fund_attention(fund, has_budget=has_active_budget)

    context = {
        **accounting_admin_site.each_context(request),
        "title": f"Fund — {fund.code}",
        "fund": fund,
        "metrics": metrics,
        "budget_rows": budgets,
        "issues": issues,
        "recent_activity": _recent_fund_activity(fund),
        "urls": {
            "workspace": reverse("accounting_admin:accounting-funds-workspace"),
            "configure": _fund_config_url(fund),
            "edit_fund": reverse("accounting_admin:accounting_fund_change", args=[fund.id]),
            "add_budget": _with_query(_admin_url("budget", "add"), fund=fund.id),
            "income": _with_query(reverse("accounting_admin:accounting-record-income"), fund=fund.id),
            "expense": _with_query(reverse("accounting_admin:accounting-record-expense"), fund=fund.id),
            "asset": _with_query(reverse("accounting_admin:accounting-purchase-fixed-asset"), fund=fund.id),
            "summary_xlsx": _fund_report_url("accounting-fund-summary", fund, "xlsx"),
            "ledger_xlsx": _fund_report_url("accounting-fund-ledger", fund, "xlsx"),
            "budget_xlsx": _fund_report_url("accounting-budget-vs-actual", fund, "xlsx"),
        },
    }
    return render(request, "admin/accounting/funds/detail.html", context)


def configure_fund_view(request, fund_id: int):
    fund = get_object_or_404(Fund, pk=fund_id)
    form = FundRestrictionForm(request.POST or None, fund=fund)

    if request.method == "POST" and form.is_valid():
        try:
            form.save()
            messages.success(request, f"Fund controls updated: {fund.code}")
            return redirect("accounting_admin:accounting-fund-detail", fund_id=fund.id)
        except Exception as exc:
            messages.error(request, f"Fund configuration failed: {exc}")

    context = {
        **accounting_admin_site.each_context(request),
        "title": f"Configure Fund Controls — {fund.code}",
        "fund": fund,
        "form": form,
        "back_url": _fund_detail_url(fund),
    }
    return render(request, "admin/accounting/funds/configure.html", context)
