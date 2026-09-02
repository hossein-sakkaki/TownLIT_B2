# apps/accounting/admin/money_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models.account import Account
from apps.accounting.models.bank import BankAccount
from apps.accounting.models.budget import Budget, BudgetLine
from apps.accounting.models.document import AccountingDocument
from apps.accounting.models.fund import Fund
from apps.accounting.services.cash_activity_service import (
    record_cash_expense,
    record_cash_income,
)

from .site import accounting_admin_site


class BankAccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        masked = f" — {obj.account_number_masked}" if obj.account_number_masked else ""
        return f"{obj.name} — {obj.institution.name}{masked} — GL {obj.ledger_account.code}"


class BudgetLineChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        fund = obj.budget.fund
        fund_label = f" — {fund.code}" if fund else ""
        return f"{obj.budget.code} / {obj.code} — {obj.name}{fund_label}"


class BaseCashForm(forms.Form):
    entry_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.localdate)
    bank_account = BankAccountChoiceField(queryset=BankAccount.objects.none())
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    description = forms.CharField(max_length=255)
    reference = forms.CharField(max_length=255, required=False)
    fund = forms.ModelChoiceField(queryset=Fund.objects.none(), required=False)
    document = forms.FileField(required=False, help_text="Optional receipt, invoice or payment proof.")

    def __init__(self, *args, fund_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fund_id = int(fund_id) if str(fund_id or "").isdigit() else None
        self.fields["bank_account"].queryset = BankAccount.objects.filter(
            status=BankAccount.STATUS_ACTIVE,
            is_active=True,
            ledger_account__is_active=True,
            ledger_account__allows_posting=True,
        ).select_related("institution", "ledger_account").order_by("-is_primary", "code")
        self.fields["fund"].queryset = Fund.objects.filter(
            status=Fund.STATUS_ACTIVE,
            is_active=True,
        ).order_by("code")
        if self.fund_id:
            self.fields["fund"].initial = self.fund_id


class CashExpenseForm(BaseCashForm):
    expense_account = forms.ModelChoiceField(queryset=Account.objects.none())
    budget_line = BudgetLineChoiceField(queryset=BudgetLine.objects.none(), required=False)

    def __init__(self, *args, fund_id=None, **kwargs):
        super().__init__(*args, fund_id=fund_id, **kwargs)
        self.fields["expense_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_EXPENSE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")
        budget_lines = BudgetLine.objects.filter(
            is_active=True,
            budget__is_active=True,
            budget__status=Budget.STATUS_ACTIVE,
        )
        if self.fund_id:
            budget_lines = budget_lines.filter(budget__fund_id=self.fund_id)
        self.fields["budget_line"].queryset = budget_lines.select_related(
            "budget", "budget__fund"
        ).order_by("budget__code", "sort_order", "code")

    def clean(self):
        data = super().clean()
        fund = data.get("fund")
        budget_line = data.get("budget_line")
        if budget_line and budget_line.budget.fund_id and (not fund or budget_line.budget.fund_id != fund.id):
            raise forms.ValidationError("The selected budget line belongs to a different fund.")
        return data


class CashIncomeForm(BaseCashForm):
    revenue_account = forms.ModelChoiceField(queryset=Account.objects.none())

    def __init__(self, *args, fund_id=None, **kwargs):
        super().__init__(*args, fund_id=fund_id, **kwargs)
        self.fields["revenue_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_REVENUE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")


def _attach_document(*, request, journal_entry, uploaded_file, reference, title, fund=None):
    if not uploaded_file:
        return
    AccountingDocument.objects.create(
        title=title,
        document_type=AccountingDocument.TYPE_RECEIPT,
        file=uploaded_file,
        journal_entry=journal_entry,
        fund=fund,
        reference=reference or "",
        uploaded_by=request.user,
    )


def money_workspace_view(request):
    recent = (
        Account.objects.none()
    )
    from apps.accounting.models.journal_entry import JournalEntry
    recent = JournalEntry.objects.filter(
        source_app="accounting_admin",
        source_model__in=("cash_income", "cash_expense"),
    ).order_by("-entry_date", "-id")[:20]

    context = {
        **accounting_admin_site.each_context(request),
        "title": "Money In & Out",
        "recent_entries": recent,
        "income_url": reverse("accounting_admin:accounting-record-income"),
        "expense_url": reverse("accounting_admin:accounting-record-expense"),
        "asset_url": reverse("accounting_admin:accounting-purchase-fixed-asset"),
    }
    return render(request, "admin/accounting/money/workspace.html", context)


def record_income_view(request):
    fund_id = request.POST.get("fund") or request.GET.get("fund")
    form = CashIncomeForm(
        request.POST or None,
        request.FILES or None,
        fund_id=fund_id,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                entry = record_cash_income(
                    entry_date=form.cleaned_data["entry_date"],
                    bank_account=form.cleaned_data["bank_account"],
                    revenue_account=form.cleaned_data["revenue_account"],
                    amount=form.cleaned_data["amount"],
                    description=form.cleaned_data["description"],
                    reference=form.cleaned_data["reference"],
                    fund=form.cleaned_data["fund"],
                    created_by=request.user,
                )
                _attach_document(
                    request=request,
                    journal_entry=entry,
                    uploaded_file=form.cleaned_data.get("document"),
                    reference=form.cleaned_data["reference"],
                    title=f"Income support - {form.cleaned_data['description']}",
                    fund=form.cleaned_data["fund"],
                )
            messages.success(request, f"Income posted: {entry.entry_number}")
            if form.cleaned_data.get("fund"):
                return redirect(
                    "accounting_admin:accounting-fund-detail",
                    fund_id=form.cleaned_data["fund"].id,
                )
            return redirect("accounting_admin:accounting-money-workspace")
        except Exception as exc:
            messages.error(request, f"Income posting failed: {exc}")

    return render(request, "admin/accounting/money/form.html", {
        **accounting_admin_site.each_context(request),
        "title": "Record Money In",
        "form": form,
        "submit_label": "Post Income",
        "help_copy": "TownLIT will debit the selected bank account and credit the selected revenue account.",
    })


def record_expense_view(request):
    fund_id = request.POST.get("fund") or request.GET.get("fund")
    form = CashExpenseForm(
        request.POST or None,
        request.FILES or None,
        fund_id=fund_id,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                entry = record_cash_expense(
                    entry_date=form.cleaned_data["entry_date"],
                    bank_account=form.cleaned_data["bank_account"],
                    expense_account=form.cleaned_data["expense_account"],
                    amount=form.cleaned_data["amount"],
                    description=form.cleaned_data["description"],
                    reference=form.cleaned_data["reference"],
                    fund=form.cleaned_data["fund"],
                    budget_line=form.cleaned_data["budget_line"],
                    created_by=request.user,
                )
                _attach_document(
                    request=request,
                    journal_entry=entry,
                    uploaded_file=form.cleaned_data.get("document"),
                    reference=form.cleaned_data["reference"],
                    title=f"Expense support - {form.cleaned_data['description']}",
                    fund=form.cleaned_data["fund"],
                )
            messages.success(request, f"Expense posted: {entry.entry_number}")
            if form.cleaned_data.get("fund"):
                return redirect(
                    "accounting_admin:accounting-fund-detail",
                    fund_id=form.cleaned_data["fund"].id,
                )
            return redirect("accounting_admin:accounting-money-workspace")
        except Exception as exc:
            messages.error(request, f"Expense posting failed: {exc}")

    return render(request, "admin/accounting/money/form.html", {
        **accounting_admin_site.each_context(request),
        "title": "Record Money Out",
        "form": form,
        "submit_label": "Post Expense",
        "help_copy": "Use this for ordinary operating costs. Use Buy Capital Asset for equipment that should remain on the balance sheet and depreciate over time.",
    })
