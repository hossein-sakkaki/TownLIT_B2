# apps/accounting/admin/fixed_asset_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models.account import Account
from apps.accounting.models.accounting_period import AccountingPeriod
from apps.accounting.models.bank import BankAccount
from apps.accounting.models.budget import Budget, BudgetLine
from apps.accounting.models.fixed_asset import FixedAsset, FixedAssetDepreciation
from apps.accounting.models.fund import Fund
from apps.accounting.services.fixed_asset_service import (
    post_depreciation_for_open_period,
    purchase_fixed_asset,
)

from .site import accounting_admin_site
from .money_admin import BankAccountChoiceField, BudgetLineChoiceField


ACCUMULATED_DEPRECIATION_CODE = "1590"
DEPRECIATION_EXPENSE_CODE = "5390"


class FixedAssetPurchaseForm(forms.Form):
    name = forms.CharField(max_length=255)
    asset_account = forms.ModelChoiceField(queryset=Account.objects.none(), label="Asset category")
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.localdate)
    placed_in_service_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.localdate)
    cost = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    salvage_value = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, initial=0)
    useful_life_years = forms.IntegerField(min_value=1, max_value=40, initial=5, label="Useful life (years)")
    bank_account = BankAccountChoiceField(queryset=BankAccount.objects.none())
    vendor_name = forms.CharField(max_length=255, required=False)
    reference = forms.CharField(max_length=255, required=False)
    serial_number = forms.CharField(max_length=255, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    fund = forms.ModelChoiceField(queryset=Fund.objects.none(), required=False)
    budget_line = BudgetLineChoiceField(queryset=BudgetLine.objects.none(), required=False)

    def __init__(self, *args, fund_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fund_id = int(fund_id) if str(fund_id or "").isdigit() else None
        self.fields["asset_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_ASSET,
            is_active=True,
            allows_posting=True,
            parent__code="1500",
        ).order_by("code")
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
        if data.get("placed_in_service_date") and data.get("purchase_date"):
            if data["placed_in_service_date"] < data["purchase_date"]:
                raise forms.ValidationError("Placed-in-service date cannot be before purchase date.")
        if data.get("cost") is not None and data.get("salvage_value") is not None:
            if data["salvage_value"] >= data["cost"]:
                raise forms.ValidationError("Salvage value must be less than cost.")
        budget_line = data.get("budget_line")
        fund = data.get("fund")
        if budget_line and budget_line.budget.fund_id and (not fund or budget_line.budget.fund_id != fund.id):
            raise forms.ValidationError("The selected budget line belongs to a different fund.")
        return data


@admin.register(FixedAsset, site=accounting_admin_site)
class FixedAssetAdmin(admin.ModelAdmin):
    list_display = (
        "asset_number", "name", "asset_account", "purchase_date", "cost",
        "accumulated_depreciation_display", "book_value_display", "status",
    )
    list_filter = ("status", "asset_account", "purchase_date")
    search_fields = ("asset_number", "name", "vendor_name", "reference", "serial_number")
    readonly_fields = (
        "asset_number", "name", "description", "asset_account", "accumulated_depreciation_account",
        "depreciation_expense_account", "acquisition_bank_account", "purchase_date", "placed_in_service_date",
        "cost", "salvage_value", "useful_life_months", "depreciation_method", "vendor_name", "reference",
        "serial_number", "fund", "budget_line", "acquisition_journal_entry", "status", "disposed_on",
        "disposal_note", "created_by", "created_at", "updated_at", "accumulated_depreciation_display",
        "book_value_display", "monthly_depreciation_display",
    )
    actions = None

    @admin.display(description="Accumulated Depreciation")
    def accumulated_depreciation_display(self, obj):
        return obj.accumulated_depreciation

    @admin.display(description="Book Value")
    def book_value_display(self, obj):
        return obj.book_value

    @admin.display(description="Monthly Depreciation")
    def monthly_depreciation_display(self, obj):
        return obj.monthly_depreciation_amount

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FixedAssetDepreciation, site=accounting_admin_site)
class FixedAssetDepreciationAdmin(admin.ModelAdmin):
    list_display = ("asset", "period_start", "period_end", "amount", "journal_entry", "posted_by", "posted_at")
    list_filter = ("period_end",)
    search_fields = ("asset__asset_number", "asset__name", "journal_entry__entry_number")
    readonly_fields = ("asset", "period_start", "period_end", "amount", "journal_entry", "posted_by", "posted_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def asset_workspace_view(request):
    open_periods = AccountingPeriod.objects.filter(
        period_type=AccountingPeriod.PERIOD_TYPE_MONTH,
        status=AccountingPeriod.STATUS_OPEN,
    ).order_by("-start_date")
    selected_period = open_periods.first()

    assets = FixedAsset.objects.select_related("asset_account", "acquisition_bank_account").prefetch_related("depreciation_entries").order_by("-purchase_date", "asset_number")

    context = {
        **accounting_admin_site.each_context(request),
        "title": "Fixed Assets",
        "assets": assets,
        "open_period": selected_period,
        "purchase_url": reverse("accounting_admin:accounting-purchase-fixed-asset"),
        "post_depreciation_url": reverse("accounting_admin:accounting-post-depreciation"),
        "setup_ready": Account.objects.filter(code=ACCUMULATED_DEPRECIATION_CODE, is_active=True, allows_posting=True).exists()
        and Account.objects.filter(code=DEPRECIATION_EXPENSE_CODE, is_active=True, allows_posting=True).exists(),
    }
    return render(request, "admin/accounting/assets/workspace.html", context)


def purchase_fixed_asset_view(request):
    accumulated = Account.objects.filter(code=ACCUMULATED_DEPRECIATION_CODE, is_active=True, allows_posting=True).first()
    depreciation_expense = Account.objects.filter(code=DEPRECIATION_EXPENSE_CODE, is_active=True, allows_posting=True).first()

    if not accumulated or not depreciation_expense:
        messages.error(request, "Fixed-asset ledger setup is incomplete. Seed accounts 1590 and 5390 first.")
        return redirect("accounting_admin:accounting-asset-workspace")

    fund_id = request.POST.get("fund") or request.GET.get("fund")
    form = FixedAssetPurchaseForm(request.POST or None, fund_id=fund_id)
    if request.method == "POST" and form.is_valid():
        try:
            asset = purchase_fixed_asset(
                name=form.cleaned_data["name"],
                purchase_date=form.cleaned_data["purchase_date"],
                placed_in_service_date=form.cleaned_data["placed_in_service_date"],
                cost=form.cleaned_data["cost"],
                salvage_value=form.cleaned_data["salvage_value"],
                useful_life_months=form.cleaned_data["useful_life_years"] * 12,
                bank_account=form.cleaned_data["bank_account"],
                asset_account=form.cleaned_data["asset_account"],
                accumulated_depreciation_account=accumulated,
                depreciation_expense_account=depreciation_expense,
                description=form.cleaned_data["description"],
                vendor_name=form.cleaned_data["vendor_name"],
                reference=form.cleaned_data["reference"],
                serial_number=form.cleaned_data["serial_number"],
                fund=form.cleaned_data["fund"],
                budget_line=form.cleaned_data["budget_line"],
                created_by=request.user,
            )
            messages.success(request, f"Capital asset created and posted: {asset.asset_number}")
            if asset.fund_id:
                return redirect(
                    "accounting_admin:accounting-fund-detail",
                    fund_id=asset.fund_id,
                )
            return redirect("accounting_admin:accounting-asset-workspace")
        except Exception as exc:
            messages.error(request, f"Capital asset purchase failed: {exc}")

    return render(request, "admin/accounting/assets/purchase.html", {
        **accounting_admin_site.each_context(request),
        "title": "Buy Capital Asset",
        "form": form,
    })


def post_depreciation_view(request):
    period_id = request.POST.get("period_id") if request.method == "POST" else None
    if request.method != "POST":
        return redirect("accounting_admin:accounting-asset-workspace")

    try:
        period = AccountingPeriod.objects.get(pk=period_id)
        result = post_depreciation_for_open_period(period=period, user=request.user)
        messages.success(
            request,
            f"Depreciation posted for {period.code}: {result['posted']} asset(s); {result['skipped']} skipped.",
        )
    except Exception as exc:
        messages.error(request, f"Depreciation posting failed: {exc}")

    return redirect("accounting_admin:accounting-asset-workspace")
