# apps/accounting/admin/vendor_ap_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.db.models import Sum
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.accounting.models import (
    Account,
    BankAccount,
    Budget,
    BudgetLine,
    Fund,
    Vendor,
    VendorAPAttachment,
    VendorBill,
    VendorBillLine,
    VendorPayment,
    VendorPaymentAllocation,
)
from apps.accounting.services.vendor_ap_service import (
    VendorAPError,
    post_vendor_bill,
    record_vendor_payment,
    refresh_bill_totals,
)

from .site import accounting_admin_site


ZERO = Decimal("0.00")


class VendorBillAdminForm(forms.ModelForm):
    class Meta:
        model = VendorBill
        fields = (
            "vendor", "bill_number", "bill_date", "due_date", "currency",
            "description", "internal_note",
        )
        widgets = {
            "bill_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_date"].required = False

    def clean(self):
        data = super().clean()
        vendor = data.get("vendor")
        bill_date = data.get("bill_date")
        due_date = data.get("due_date")
        if vendor and bill_date and not due_date:
            data["due_date"] = bill_date + timedelta(days=vendor.default_terms_days or 0)
        return data


class VendorBillLineForm(forms.ModelForm):
    class Meta:
        model = VendorBillLine
        fields = (
            "line_number", "description", "account", "amount", "tax_amount", "tax_account",
            "fund", "budget_line", "capitalize_as_fixed_asset", "asset_name",
            "placed_in_service_date", "useful_life_months", "salvage_value", "serial_number",
        )
        widgets = {
            "placed_in_service_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(
            account_type__in=(Account.TYPE_EXPENSE, Account.TYPE_ASSET),
            is_active=True,
            allows_posting=True,
        ).order_by("account_type", "code")
        self.fields["tax_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_ASSET,
            is_active=True,
            allows_posting=True,
            parent__code="1400",
        ).order_by("code")
        self.fields["fund"].queryset = Fund.objects.filter(
            status=Fund.STATUS_ACTIVE,
            is_active=True,
        ).order_by("code")
        self.fields["budget_line"].queryset = BudgetLine.objects.filter(
            is_active=True,
            budget__is_active=True,
            budget__status=Budget.STATUS_ACTIVE,
        ).select_related("budget", "budget__fund").order_by("budget__code", "sort_order", "code")


class VendorBillLineInline(admin.TabularInline):
    model = VendorBillLine
    form = VendorBillLineForm
    extra = 1
    autocomplete_fields = ("account", "tax_account", "fund", "budget_line")
    fields = (
        "line_number", "description", "account", "amount", "tax_amount", "tax_account",
        "fund", "budget_line", "capitalize_as_fixed_asset", "asset_name",
        "placed_in_service_date", "useful_life_months", "salvage_value", "serial_number",
        "fixed_asset",
    )
    readonly_fields = ("fixed_asset",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.posting_journal_entry_id:
            return self.fields
        return ("fixed_asset",)

    def has_add_permission(self, request, obj):
        return not bool(obj and obj.posting_journal_entry_id)

    def has_delete_permission(self, request, obj=None):
        return not bool(obj and obj.posting_journal_entry_id)


class BillAttachmentInline(admin.TabularInline):
    model = VendorAPAttachment
    fk_name = "bill"
    extra = 0
    fields = ("document_type", "title", "file", "uploaded_by", "created_at")
    readonly_fields = ("uploaded_by", "created_at")

class PaymentAllocationInline(admin.TabularInline):
    model = VendorPaymentAllocation
    extra = 0
    fields = ("bill", "amount", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


class PaymentAttachmentInline(admin.TabularInline):
    model = VendorAPAttachment
    fk_name = "payment"
    extra = 0
    fields = ("document_type", "title", "file", "uploaded_by", "created_at")
    readonly_fields = ("uploaded_by", "created_at")
    can_delete = False


@admin.register(Vendor, site=accounting_admin_site)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name_display", "email", "default_terms_days",
        "default_payment_method", "outstanding_display", "is_active",
    )
    list_filter = ("is_active", "default_payment_method", "country")
    search_fields = ("code", "legal_name", "display_name", "email", "account_number_with_vendor")
    ordering = ("display_name", "legal_name")
    readonly_fields = ("created_at", "updated_at", "outstanding_display")

    fieldsets = (
        ("Vendor", {"fields": ("code", "legal_name", "display_name", "is_active")}),
        ("Payment Terms", {"fields": ("default_terms_days", "default_payment_method", "account_number_with_vendor", "tax_registration_number")}),
        ("Contact", {"fields": ("email", "phone", "website", "address_line1", "address_line2", "city", "province", "postal_code", "country")}),
        ("Summary", {"fields": ("outstanding_display",)}),
        ("Internal", {"fields": ("internal_note", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Vendor")
    def name_display(self, obj):
        return obj.display_name or obj.legal_name

    @admin.display(description="Outstanding")
    def outstanding_display(self, obj):
        outstanding = sum(
            (bill.outstanding_amount for bill in obj.bills.filter(status__in=(VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL))),
            ZERO,
        )
        return outstanding


@admin.register(VendorBill, site=accounting_admin_site)
class VendorBillAdmin(admin.ModelAdmin):
    form = VendorBillAdminForm
    change_form_template = "admin/accounting/vendor_bill/change_form.html"
    inlines = (VendorBillLineInline, BillAttachmentInline)
    list_display = (
        "vendor", "bill_number", "bill_date", "due_date", "total_amount",
        "amount_paid", "outstanding_display", "status", "action_link",
    )
    list_filter = ("status", "vendor", "bill_date", "due_date", "currency")
    search_fields = ("vendor__legal_name", "vendor__display_name", "vendor__code", "bill_number", "description")
    ordering = ("-bill_date", "-id")
    autocomplete_fields = ("vendor",)
    readonly_fields = (
        "subtotal", "tax_total", "total_amount", "amount_paid", "outstanding_display",
        "status", "posting_journal_entry", "posted_at", "posted_by", "created_by", "created_at", "updated_at",
    )

    fieldsets = (
        ("Invoice", {"fields": ("vendor", "bill_number", "bill_date", "due_date", "currency", "description")}),
        ("Amounts", {"fields": ("subtotal", "tax_total", "total_amount", "amount_paid", "outstanding_display", "status")}),
        ("Ledger", {"fields": ("posting_journal_entry", "posted_at", "posted_by")}),
        ("Internal", {"fields": ("internal_note", "created_by", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:object_id>/post-bill/",
                self.admin_site.admin_view(self.post_bill_view),
                name="accounting_vendorbill_post",
            ),
        ]
        return custom + urls

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.posting_journal_entry_id:
            readonly.extend(("vendor", "bill_number", "bill_date", "due_date", "currency", "description", "internal_note"))
        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for instance in instances:
            if isinstance(instance, VendorAPAttachment) and not instance.uploaded_by_id:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        bill = form.instance
        if not bill.posting_journal_entry_id:
            refresh_bill_totals(bill=bill)

    def has_delete_permission(self, request, obj=None):
        return not bool(obj and obj.posting_journal_entry_id)

    @admin.display(description="Outstanding")
    def outstanding_display(self, obj):
        return obj.outstanding_amount

    @admin.display(description="Next")
    def action_link(self, obj):
        if obj.status == VendorBill.STATUS_DRAFT:
            url = reverse("accounting_admin:accounting_vendorbill_change", args=[obj.pk])
            return format_html('<a href="{}">Review & Post</a>', url)
        if obj.status in {VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL}:
            url = reverse("accounting_admin:accounting-ap-pay-vendor", args=[obj.vendor_id]) + f"?bill_id={obj.pk}"
            return format_html('<a href="{}">Pay</a>', url)
        return "—"

    def post_bill_view(self, request, object_id):
        bill = get_object_or_404(VendorBill, pk=object_id)
        if request.method != "POST":
            return redirect("accounting_admin:accounting_vendorbill_change", object_id)
        try:
            posted = post_vendor_bill(bill=bill, user=request.user)
            messages.success(request, f"Bill {posted.bill_number} posted to Accounts Payable.")
        except Exception as exc:
            messages.error(request, f"Bill posting failed: {exc}")
        return redirect("accounting_admin:accounting_vendorbill_change", object_id)


@admin.register(VendorPayment, site=accounting_admin_site)
class VendorPaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_number", "vendor", "payment_date", "bank_account", "amount", "currency", "payment_method", "reference", "journal_entry")
    list_filter = ("vendor", "bank_account", "payment_method", "payment_date")
    search_fields = ("payment_number", "vendor__legal_name", "vendor__display_name", "reference", "journal_entry__entry_number")
    readonly_fields = (
        "payment_number", "vendor", "payment_date", "bank_account", "amount", "currency",
        "payment_method", "reference", "note", "journal_entry", "created_by", "created_at",
    )
    inlines = (PaymentAllocationInline, PaymentAttachmentInline)

    def has_add_permission(self, request):
        return False

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for instance in instances:
            if isinstance(instance, VendorAPAttachment) and not instance.uploaded_by_id:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VendorPaymentAllocation, site=accounting_admin_site)
class VendorPaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ("payment", "bill", "amount", "created_at")
    list_filter = ("bill__vendor", "created_at")
    search_fields = ("payment__payment_number", "bill__bill_number", "bill__vendor__legal_name")
    readonly_fields = ("payment", "bill", "amount", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VendorAPAttachment, site=accounting_admin_site)
class VendorAPAttachmentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "bill", "payment", "uploaded_by", "created_at")
    list_filter = ("document_type", "created_at")
    search_fields = ("title", "bill__bill_number", "payment__payment_number")
    readonly_fields = ("bill", "payment", "document_type", "title", "file", "uploaded_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class VendorPaymentForm(forms.Form):
    payment_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.localdate)
    bank_account = forms.ModelChoiceField(queryset=BankAccount.objects.none())
    payment_method = forms.ChoiceField(choices=Vendor.PAYMENT_METHOD_CHOICES)
    reference = forms.CharField(max_length=255)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    payment_proof = forms.FileField(required=False)

    def __init__(self, *args, vendor, preselected_bill_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = vendor
        self.preselected_bill_id = int(preselected_bill_id) if str(preselected_bill_id or "").isdigit() else None
        self.fields["payment_method"].initial = vendor.default_payment_method
        self.fields["bank_account"].queryset = BankAccount.objects.filter(
            status=BankAccount.STATUS_ACTIVE,
            is_active=True,
            ledger_account__is_active=True,
            ledger_account__allows_posting=True,
        ).select_related("institution", "ledger_account").order_by("-is_primary", "code")

        self.bill_rows = []
        bills = vendor.bills.filter(
            status__in=(VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL),
            posting_journal_entry__isnull=False,
        ).order_by("due_date", "bill_date", "id")
        for bill in bills:
            field_name = f"bill_{bill.id}"
            self.fields[field_name] = forms.DecimalField(
                max_digits=14,
                decimal_places=2,
                min_value=0,
                required=False,
                initial=(bill.outstanding_amount if bill.id == self.preselected_bill_id else ZERO),
            )
            self.bill_rows.append((bill, field_name))

    def clean(self):
        data = super().clean()
        allocations = []
        for bill, field_name in self.bill_rows:
            amount = data.get(field_name) or ZERO
            if amount > ZERO:
                if amount > bill.outstanding_amount:
                    self.add_error(field_name, f"Cannot exceed outstanding amount {bill.outstanding_amount}.")
                else:
                    allocations.append((bill, amount))
        if not allocations:
            raise forms.ValidationError("Enter a payment amount for at least one bill.")

        bank_account = data.get("bank_account")
        bill_currencies = {bill.currency for bill, _ in allocations}
        if len(bill_currencies) > 1:
            raise forms.ValidationError("One payment cannot mix bills with different currencies.")
        if bank_account and bill_currencies:
            bill_currency = next(iter(bill_currencies))
            if bill_currency != bank_account.currency:
                self.add_error(
                    "bank_account",
                    f"Selected bills are in {bill_currency}; choose a {bill_currency} bank account. "
                    "Foreign-currency payments require an FX workflow.",
                )

        data["allocations"] = allocations
        return data


def _aging_bucket(bill, today):
    if bill.due_date >= today:
        return "current"
    days = (today - bill.due_date).days
    if days <= 30:
        return "days_1_30"
    if days <= 60:
        return "days_31_60"
    if days <= 90:
        return "days_61_90"
    return "days_90_plus"


def build_ap_workspace_context():
    today = timezone.localdate()
    open_bills = list(
        VendorBill.objects.filter(
            status__in=(VendorBill.STATUS_OPEN, VendorBill.STATUS_PARTIAL),
            posting_journal_entry__isnull=False,
        ).select_related("vendor", "posting_journal_entry").order_by("due_date", "vendor__legal_name")
    )

    aging = {"current": ZERO, "days_1_30": ZERO, "days_31_60": ZERO, "days_61_90": ZERO, "days_90_plus": ZERO}
    rows = []
    vendor_totals = {}
    for bill in open_bills:
        outstanding = bill.outstanding_amount
        bucket = _aging_bucket(bill, today)
        aging[bucket] += outstanding
        vendor_totals.setdefault(bill.vendor_id, {"vendor": bill.vendor, "outstanding": ZERO, "overdue": ZERO})
        vendor_totals[bill.vendor_id]["outstanding"] += outstanding
        if bill.due_date < today:
            vendor_totals[bill.vendor_id]["overdue"] += outstanding
        rows.append({
            "bill": bill,
            "outstanding": outstanding,
            "bucket": bucket,
            "days_overdue": max((today - bill.due_date).days, 0),
        })

    overdue_total = aging["days_1_30"] + aging["days_31_60"] + aging["days_61_90"] + aging["days_90_plus"]
    due_next_7 = sum(
        (row["outstanding"] for row in rows if today <= row["bill"].due_date <= today + timedelta(days=7)),
        ZERO,
    )

    return {
        "ap_today": today,
        "ap_open_total": sum((row["outstanding"] for row in rows), ZERO),
        "ap_overdue_total": overdue_total,
        "ap_due_next_7": due_next_7,
        "ap_aging": aging,
        "ap_rows": rows,
        "ap_vendor_rows": sorted(vendor_totals.values(), key=lambda item: item["outstanding"], reverse=True),
        "ap_draft_count": VendorBill.objects.filter(status=VendorBill.STATUS_DRAFT).count(),
        "ap_overdue_count": sum(1 for row in rows if row["bill"].due_date < today),
    }


def accounts_payable_workspace_view(request):
    context = {
        **accounting_admin_site.each_context(request),
        **build_ap_workspace_context(),
        "title": "Bills & Accounts Payable",
        "add_bill_url": reverse("accounting_admin:accounting_vendorbill_add"),
        "add_vendor_url": reverse("accounting_admin:accounting_vendor_add"),
        "vendors_url": reverse("accounting_admin:accounting_vendor_changelist"),
        "payments_url": reverse("accounting_admin:accounting_vendorpayment_changelist"),
        "aging_export_url": reverse("accounting_admin:accounting-ap-aging-export"),
    }
    return render(request, "admin/accounting/ap/workspace.html", context)


def pay_vendor_view(request, vendor_id):
    vendor = get_object_or_404(Vendor, pk=vendor_id, is_active=True)
    preselected = request.GET.get("bill_id") or request.POST.get("preselected_bill_id")
    form = VendorPaymentForm(
        request.POST or None,
        request.FILES or None,
        vendor=vendor,
        preselected_bill_id=preselected,
    )

    if request.method == "POST" and form.is_valid():
        try:
            payment = record_vendor_payment(
                vendor=vendor,
                allocations=form.cleaned_data["allocations"],
                payment_date=form.cleaned_data["payment_date"],
                bank_account=form.cleaned_data["bank_account"],
                payment_method=form.cleaned_data["payment_method"],
                reference=form.cleaned_data["reference"],
                note=form.cleaned_data["note"],
                user=request.user,
            )
            proof = form.cleaned_data.get("payment_proof")
            if proof:
                VendorAPAttachment.objects.create(
                    payment=payment,
                    document_type=VendorAPAttachment.TYPE_PAYMENT_PROOF,
                    title=f"Payment proof - {payment.payment_number}",
                    file=proof,
                    uploaded_by=request.user,
                )
            messages.success(request, f"Vendor payment posted: {payment.payment_number} — {payment.amount}")
            return redirect("accounting_admin:accounting-ap-workspace")
        except Exception as exc:
            messages.error(request, f"Vendor payment failed: {exc}")

    rows = []
    for bill, field_name in form.bill_rows:
        rows.append({"bill": bill, "field": form[field_name]})

    return render(request, "admin/accounting/ap/pay_vendor.html", {
        **accounting_admin_site.each_context(request),
        "title": f"Pay Vendor — {vendor}",
        "vendor": vendor,
        "form": form,
        "bill_rows": rows,
        "preselected_bill_id": preselected or "",
    })


def ap_aging_export_view(request):
    import csv
    from io import StringIO

    context = build_ap_workspace_context()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Vendor", "Bill", "Bill Date", "Due Date", "Total", "Paid", "Outstanding", "Days Overdue", "Status"])
    for row in context["ap_rows"]:
        bill = row["bill"]
        writer.writerow([
            str(bill.vendor), bill.bill_number, bill.bill_date, bill.due_date,
            bill.total_amount, bill.amount_paid, row["outstanding"], row["days_overdue"], bill.status,
        ])

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="townlit-ap-aging-{timezone.localdate()}.csv"'
    return response
