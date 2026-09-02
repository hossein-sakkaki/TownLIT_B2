# apps/accounting/admin/customer_ar_admin.py
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
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.accounting.models import (
    Account,
    BankAccount,
    Customer,
    CustomerARAttachment,
    CustomerInvoice,
    CustomerInvoiceLine,
    CustomerReceipt,
    CustomerReceiptAllocation,
    Fund,
)
from apps.accounting.services.customer_ar_service import (
    post_customer_invoice,
    record_customer_receipt,
    refresh_invoice_totals,
)

from .site import accounting_admin_site


ZERO = Decimal("0.00")


class CustomerAdminForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_receivable_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_ASSET,
            is_active=True,
            allows_posting=True,
            parent__code="1100",
        ).order_by("code")
        self.fields["default_revenue_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_REVENUE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")


class CustomerInvoiceAdminForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    receivable_account = forms.ModelChoiceField(
        required=False,
        queryset=Account.objects.none(),
    )

    class Meta:
        model = CustomerInvoice
        fields = (
            "customer",
            "invoice_number",
            "invoice_date",
            "due_date",
            "receivable_account",
            "currency",
            "description",
            "purchase_order_reference",
            "sent_at",
            "internal_note",
        )
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "sent_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice_number"].required = False
        self.fields["receivable_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_ASSET,
            is_active=True,
            allows_posting=True,
            parent__code="1100",
        ).order_by("code")

    def clean(self):
        data = super().clean()
        customer = data.get("customer")
        invoice_date = data.get("invoice_date")

        if customer and invoice_date and not data.get("due_date"):
            data["due_date"] = invoice_date + timedelta(days=customer.default_terms_days or 0)
        if customer and not data.get("receivable_account"):
            data["receivable_account"] = customer.default_receivable_account
        return data


class CustomerInvoiceLineForm(forms.ModelForm):
    class Meta:
        model = CustomerInvoiceLine
        fields = (
            "line_number",
            "description",
            "quantity",
            "unit_price",
            "revenue_account",
            "tax_amount",
            "tax_account",
            "fund",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["revenue_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_REVENUE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")
        self.fields["tax_account"].queryset = Account.objects.filter(
            code="2310",
            account_type=Account.TYPE_LIABILITY,
            is_active=True,
            allows_posting=True,
        ).order_by("code")
        self.fields["fund"].queryset = Fund.objects.filter(
            status=Fund.STATUS_ACTIVE,
            is_active=True,
        ).order_by("code")


class CustomerInvoiceLineInline(admin.TabularInline):
    model = CustomerInvoiceLine
    form = CustomerInvoiceLineForm
    extra = 1
    fields = (
        "line_number",
        "description",
        "quantity",
        "unit_price",
        "amount",
        "revenue_account",
        "tax_amount",
        "tax_account",
        "fund",
    )
    readonly_fields = ("amount",)
    autocomplete_fields = ("revenue_account", "tax_account", "fund")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.posting_journal_entry_id:
            return self.fields
        return ("amount",)

    def has_add_permission(self, request, obj):
        return not bool(obj and obj.posting_journal_entry_id)

    def has_delete_permission(self, request, obj=None):
        return not bool(obj and obj.posting_journal_entry_id)


class InvoiceAttachmentInline(admin.TabularInline):
    model = CustomerARAttachment
    fk_name = "invoice"
    extra = 0
    fields = ("document_type", "title", "file", "uploaded_by", "created_at")
    readonly_fields = ("uploaded_by", "created_at")


class ReceiptAllocationInline(admin.TabularInline):
    model = CustomerReceiptAllocation
    extra = 0
    fields = ("invoice", "amount", "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


class ReceiptAttachmentInline(admin.TabularInline):
    model = CustomerARAttachment
    fk_name = "receipt"
    extra = 0
    fields = ("document_type", "title", "file", "uploaded_by", "created_at")
    readonly_fields = ("uploaded_by", "created_at")
    can_delete = False


@admin.register(Customer, site=accounting_admin_site)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm
    list_display = (
        "code",
        "name_display",
        "billing_email",
        "default_terms_days",
        "default_receivable_account",
        "outstanding_display",
        "is_active",
        "receive_link",
    )
    list_filter = ("is_active", "default_payment_method", "country")
    search_fields = (
        "code",
        "legal_name",
        "display_name",
        "billing_email",
        "customer_reference",
    )
    ordering = ("display_name", "legal_name")
    readonly_fields = ("created_at", "updated_at", "outstanding_display")
    autocomplete_fields = ("default_receivable_account", "default_revenue_account")

    fieldsets = (
        ("Customer", {"fields": ("code", "legal_name", "display_name", "is_active")}),
        (
            "Billing & Accounts Receivable",
            {
                "fields": (
                    "default_terms_days",
                    "default_payment_method",
                    "default_receivable_account",
                    "default_revenue_account",
                    "customer_reference",
                    "tax_registration_number",
                )
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    "billing_email",
                    "phone",
                    "website",
                    "address_line1",
                    "address_line2",
                    "city",
                    "province",
                    "postal_code",
                    "country",
                )
            },
        ),
        ("Summary", {"fields": ("outstanding_display",)}),
        ("Internal", {"fields": ("internal_note", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Customer")
    def name_display(self, obj):
        return obj.display_name or obj.legal_name

    @admin.display(description="Outstanding")
    def outstanding_display(self, obj):
        return sum(
            (
                invoice.outstanding_amount
                for invoice in obj.invoices.filter(
                    status__in=(CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL)
                )
            ),
            ZERO,
        )

    @admin.display(description="Action")
    def receive_link(self, obj):
        if not obj.is_active:
            return "—"
        url = reverse("accounting_admin:accounting-ar-receive-customer", args=[obj.id])
        return format_html('<a href="{}">Receive payment</a>', url)


@admin.register(CustomerInvoice, site=accounting_admin_site)
class CustomerInvoiceAdmin(admin.ModelAdmin):
    form = CustomerInvoiceAdminForm
    change_form_template = "admin/accounting/customer_invoice/change_form.html"
    inlines = (CustomerInvoiceLineInline, InvoiceAttachmentInline)
    list_display = (
        "invoice_number",
        "customer",
        "invoice_date",
        "due_date",
        "total_amount",
        "amount_received",
        "outstanding_display",
        "status",
        "sent_at",
        "action_link",
    )
    list_filter = ("status", "customer", "invoice_date", "due_date", "currency")
    search_fields = (
        "invoice_number",
        "customer__legal_name",
        "customer__display_name",
        "customer__code",
        "description",
        "purchase_order_reference",
    )
    ordering = ("-invoice_date", "-id")
    autocomplete_fields = ("customer", "receivable_account")
    readonly_fields = (
        "subtotal",
        "tax_total",
        "total_amount",
        "amount_received",
        "outstanding_display",
        "status",
        "posting_journal_entry",
        "posted_at",
        "posted_by",
        "created_by",
        "created_at",
        "updated_at",
    )
    actions = ("mark_selected_as_sent",)

    fieldsets = (
        (
            "Invoice",
            {
                "fields": (
                    "customer",
                    "invoice_number",
                    "invoice_date",
                    "due_date",
                    "receivable_account",
                    "currency",
                    "description",
                    "purchase_order_reference",
                )
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "subtotal",
                    "tax_total",
                    "total_amount",
                    "amount_received",
                    "outstanding_display",
                    "status",
                )
            },
        ),
        ("Delivery", {"fields": ("sent_at",)}),
        ("Ledger", {"fields": ("posting_journal_entry", "posted_at", "posted_by")}),
        (
            "Internal",
            {"fields": ("internal_note", "created_by", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:object_id>/post-invoice/",
                self.admin_site.admin_view(self.post_invoice_view),
                name="accounting_customerinvoice_post",
            ),
        ]
        return custom + urls

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.posting_journal_entry_id:
            readonly.extend(
                (
                    "customer",
                    "invoice_number",
                    "invoice_date",
                    "due_date",
                    "receivable_account",
                    "currency",
                    "description",
                    "purchase_order_reference",
                )
            )
        return tuple(dict.fromkeys(readonly))

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        raw_customer = request.GET.get("customer")
        if raw_customer and raw_customer.isdigit():
            customer = Customer.objects.filter(pk=int(raw_customer), is_active=True).first()
            if customer:
                initial["customer"] = customer.pk
                initial["receivable_account"] = customer.default_receivable_account_id
                initial["invoice_date"] = timezone.localdate()
                initial["due_date"] = timezone.localdate() + timedelta(days=customer.default_terms_days or 0)
        return initial

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for instance in instances:
            if isinstance(instance, CustomerARAttachment) and not instance.uploaded_by_id:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        invoice = form.instance
        if not invoice.posting_journal_entry_id:
            refresh_invoice_totals(invoice=invoice)

    def has_delete_permission(self, request, obj=None):
        return not bool(obj and obj.posting_journal_entry_id)

    @admin.display(description="Outstanding")
    def outstanding_display(self, obj):
        return obj.outstanding_amount

    @admin.display(description="Next")
    def action_link(self, obj):
        if obj.status == CustomerInvoice.STATUS_DRAFT:
            url = reverse("accounting_admin:accounting_customerinvoice_change", args=[obj.pk])
            return format_html('<a href="{}">Review & Post</a>', url)
        if obj.status in {CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL}:
            url = reverse("accounting_admin:accounting-ar-receive-customer", args=[obj.customer_id])
            return format_html('<a href="{}?invoice_id={}">Receive</a>', url, obj.pk)
        return "—"

    @admin.action(description="Mark selected invoices as sent")
    def mark_selected_as_sent(self, request, queryset):
        updated = queryset.exclude(status=CustomerInvoice.STATUS_DRAFT).filter(sent_at__isnull=True).update(
            sent_at=timezone.now()
        )
        self.message_user(request, f"{updated} invoice(s) marked as sent.", level=messages.SUCCESS)

    def post_invoice_view(self, request, object_id):
        invoice = get_object_or_404(
            CustomerInvoice.objects.select_related("customer", "receivable_account"),
            pk=object_id,
        )
        if request.method == "POST":
            try:
                posted = post_customer_invoice(invoice=invoice, user=request.user)
                messages.success(
                    request,
                    f"Invoice {posted.invoice_number} posted to Accounts Receivable.",
                )
                return redirect("accounting_admin:accounting_customerinvoice_change", object_id)
            except Exception as exc:
                messages.error(request, f"Invoice posting failed: {exc}")
                return redirect("accounting_admin:accounting_customerinvoice_change", object_id)

        return render(
            request,
            "admin/accounting/customer_invoice/post_confirm.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Post Invoice {invoice.invoice_number}",
                "invoice": invoice,
                "cancel_url": reverse(
                    "accounting_admin:accounting_customerinvoice_change",
                    args=[invoice.id],
                ),
            },
        )


@admin.register(CustomerReceipt, site=accounting_admin_site)
class CustomerReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "customer",
        "receipt_date",
        "bank_account",
        "amount",
        "currency",
        "payment_method",
        "reference",
        "journal_entry",
    )
    list_filter = ("customer", "bank_account", "payment_method", "receipt_date")
    search_fields = (
        "receipt_number",
        "customer__legal_name",
        "customer__display_name",
        "reference",
        "journal_entry__entry_number",
    )
    readonly_fields = (
        "receipt_number",
        "customer",
        "receipt_date",
        "bank_account",
        "amount",
        "currency",
        "payment_method",
        "reference",
        "note",
        "journal_entry",
        "created_by",
        "created_at",
    )
    inlines = (ReceiptAllocationInline, ReceiptAttachmentInline)

    def has_add_permission(self, request):
        return False

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for deleted in formset.deleted_objects:
            deleted.delete()
        for instance in instances:
            if isinstance(instance, CustomerARAttachment) and not instance.uploaded_by_id:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerReceiptAllocation, site=accounting_admin_site)
class CustomerReceiptAllocationAdmin(admin.ModelAdmin):
    list_display = ("receipt", "invoice", "amount", "created_at")
    list_filter = ("invoice__customer", "created_at")
    search_fields = (
        "receipt__receipt_number",
        "invoice__invoice_number",
        "invoice__customer__legal_name",
    )
    readonly_fields = ("receipt", "invoice", "amount", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerARAttachment, site=accounting_admin_site)
class CustomerARAttachmentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "invoice", "receipt", "uploaded_by", "created_at")
    list_filter = ("document_type", "created_at")
    search_fields = ("title", "invoice__invoice_number", "receipt__receipt_number")
    readonly_fields = ("invoice", "receipt", "document_type", "title", "file", "uploaded_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CustomerReceiptForm(forms.Form):
    receipt_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )
    bank_account = forms.ModelChoiceField(queryset=BankAccount.objects.none())
    payment_method = forms.ChoiceField(choices=Customer.PAYMENT_METHOD_CHOICES)
    reference = forms.CharField(max_length=255)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    receipt_proof = forms.FileField(required=False)

    def __init__(self, *args, customer, preselected_invoice_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.customer = customer
        self.preselected_invoice_id = (
            int(preselected_invoice_id)
            if str(preselected_invoice_id or "").isdigit()
            else None
        )
        self.fields["payment_method"].initial = customer.default_payment_method
        self.fields["bank_account"].queryset = BankAccount.objects.filter(
            status=BankAccount.STATUS_ACTIVE,
            is_active=True,
            ledger_account__is_active=True,
            ledger_account__allows_posting=True,
        ).select_related("institution", "ledger_account").order_by("-is_primary", "code")

        self.invoice_rows = []
        invoices = customer.invoices.filter(
            status__in=(CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL),
            posting_journal_entry__isnull=False,
        ).select_related("receivable_account").order_by("due_date", "invoice_date", "id")

        for invoice in invoices:
            field_name = f"invoice_{invoice.id}"
            self.fields[field_name] = forms.DecimalField(
                max_digits=14,
                decimal_places=2,
                min_value=0,
                required=False,
                initial=(
                    invoice.outstanding_amount
                    if invoice.id == self.preselected_invoice_id
                    else ZERO
                ),
            )
            self.invoice_rows.append((invoice, field_name))

    def clean(self):
        data = super().clean()
        allocations = []
        for invoice, field_name in self.invoice_rows:
            amount = data.get(field_name) or ZERO
            if amount > ZERO:
                if amount > invoice.outstanding_amount:
                    self.add_error(
                        field_name,
                        f"Cannot exceed outstanding amount {invoice.outstanding_amount}.",
                    )
                else:
                    allocations.append((invoice, amount))

        if not allocations:
            raise forms.ValidationError("Enter a receipt amount for at least one invoice.")

        bank_account = data.get("bank_account")
        invoice_currencies = {invoice.currency for invoice, _ in allocations}
        if len(invoice_currencies) > 1:
            raise forms.ValidationError("One receipt cannot mix invoices with different currencies.")
        if bank_account and invoice_currencies:
            invoice_currency = next(iter(invoice_currencies))
            if invoice_currency != bank_account.currency:
                self.add_error(
                    "bank_account",
                    f"Selected invoices are in {invoice_currency}; choose a {invoice_currency} bank account. "
                    "Foreign-currency receipts require an FX workflow.",
                )

        data["allocations"] = allocations
        return data


def _aging_bucket(invoice, today):
    if invoice.due_date >= today:
        return "current"
    days = (today - invoice.due_date).days
    if days <= 30:
        return "days_1_30"
    if days <= 60:
        return "days_31_60"
    if days <= 90:
        return "days_61_90"
    return "days_90_plus"


def build_ar_workspace_context():
    today = timezone.localdate()
    open_invoices = list(
        CustomerInvoice.objects.filter(
            status__in=(CustomerInvoice.STATUS_OPEN, CustomerInvoice.STATUS_PARTIAL),
            posting_journal_entry__isnull=False,
        )
        .select_related("customer", "receivable_account", "posting_journal_entry")
        .order_by("due_date", "customer__legal_name")
    )

    aging = {
        "current": ZERO,
        "days_1_30": ZERO,
        "days_31_60": ZERO,
        "days_61_90": ZERO,
        "days_90_plus": ZERO,
    }
    rows = []
    customer_totals = {}

    for invoice in open_invoices:
        outstanding = invoice.outstanding_amount
        bucket = _aging_bucket(invoice, today)
        aging[bucket] += outstanding
        customer_totals.setdefault(
            invoice.customer_id,
            {"customer": invoice.customer, "outstanding": ZERO, "overdue": ZERO},
        )
        customer_totals[invoice.customer_id]["outstanding"] += outstanding
        if invoice.due_date < today:
            customer_totals[invoice.customer_id]["overdue"] += outstanding

        rows.append(
            {
                "invoice": invoice,
                "outstanding": outstanding,
                "bucket": bucket,
                "days_overdue": max((today - invoice.due_date).days, 0),
                "change_url": reverse(
                    "accounting_admin:accounting_customerinvoice_change",
                    args=[invoice.id],
                ),
                "receive_url": (
                    reverse(
                        "accounting_admin:accounting-ar-receive-customer",
                        args=[invoice.customer_id],
                    )
                    + f"?invoice_id={invoice.id}"
                ),
                "print_url": reverse(
                    "accounting_admin:accounting-ar-invoice-print",
                    args=[invoice.id],
                ),
            }
        )

    overdue_total = (
        aging["days_1_30"]
        + aging["days_31_60"]
        + aging["days_61_90"]
        + aging["days_90_plus"]
    )
    due_next_7 = sum(
        (
            row["outstanding"]
            for row in rows
            if today <= row["invoice"].due_date <= today + timedelta(days=7)
        ),
        ZERO,
    )

    customer_rows = []
    for item in sorted(
        customer_totals.values(),
        key=lambda value: value["outstanding"],
        reverse=True,
    ):
        customer = item["customer"]
        item["receive_url"] = reverse(
            "accounting_admin:accounting-ar-receive-customer",
            args=[customer.id],
        )
        item["statement_url"] = reverse(
            "accounting_admin:accounting-ar-customer-statement",
            args=[customer.id],
        )
        customer_rows.append(item)

    return {
        "ar_today": today,
        "ar_open_total": sum((row["outstanding"] for row in rows), ZERO),
        "ar_overdue_total": overdue_total,
        "ar_due_next_7": due_next_7,
        "ar_aging": aging,
        "ar_rows": rows,
        "ar_customer_rows": customer_rows,
        "ar_draft_count": CustomerInvoice.objects.filter(status=CustomerInvoice.STATUS_DRAFT).count(),
        "ar_overdue_count": sum(1 for row in rows if row["invoice"].due_date < today),
    }


def accounts_receivable_workspace_view(request):
    context = {
        **accounting_admin_site.each_context(request),
        **build_ar_workspace_context(),
        "title": "Invoices & Accounts Receivable",
        "add_invoice_url": reverse("accounting_admin:accounting_customerinvoice_add"),
        "add_customer_url": reverse("accounting_admin:accounting_customer_add"),
        "customers_url": reverse("accounting_admin:accounting_customer_changelist"),
        "receipts_url": reverse("accounting_admin:accounting_customerreceipt_changelist"),
        "aging_export_url": reverse("accounting_admin:accounting-ar-aging-export"),
    }
    return render(request, "admin/accounting/ar/workspace.html", context)


def receive_customer_payment_view(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id, is_active=True)
    preselected = request.GET.get("invoice_id") or request.POST.get("preselected_invoice_id")
    form = CustomerReceiptForm(
        request.POST or None,
        request.FILES or None,
        customer=customer,
        preselected_invoice_id=preselected,
    )

    if request.method == "POST" and form.is_valid():
        try:
            receipt = record_customer_receipt(
                customer=customer,
                allocations=form.cleaned_data["allocations"],
                receipt_date=form.cleaned_data["receipt_date"],
                bank_account=form.cleaned_data["bank_account"],
                payment_method=form.cleaned_data["payment_method"],
                reference=form.cleaned_data["reference"],
                note=form.cleaned_data["note"],
                user=request.user,
            )
            proof = form.cleaned_data.get("receipt_proof")
            if proof:
                CustomerARAttachment.objects.create(
                    receipt=receipt,
                    document_type=CustomerARAttachment.TYPE_RECEIPT_PROOF,
                    title=f"Receipt proof - {receipt.receipt_number}",
                    file=proof,
                    uploaded_by=request.user,
                )
            messages.success(
                request,
                f"Customer receipt posted: {receipt.receipt_number} — {receipt.amount}",
            )
            return redirect("accounting_admin:accounting-ar-workspace")
        except Exception as exc:
            messages.error(request, f"Customer receipt failed: {exc}")

    rows = [
        {"invoice": invoice, "field": form[field_name]}
        for invoice, field_name in form.invoice_rows
    ]

    return render(
        request,
        "admin/accounting/ar/receive_customer_payment.html",
        {
            **accounting_admin_site.each_context(request),
            "title": f"Receive Payment — {customer}",
            "customer": customer,
            "form": form,
            "invoice_rows": rows,
            "preselected_invoice_id": preselected or "",
        },
    )


def ar_aging_export_view(request):
    import csv
    from io import StringIO

    context = build_ar_workspace_context()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Customer",
            "Invoice",
            "Invoice Date",
            "Due Date",
            "Total",
            "Received",
            "Outstanding",
            "Days Overdue",
            "Status",
        ]
    )
    for row in context["ar_rows"]:
        invoice = row["invoice"]
        writer.writerow(
            [
                str(invoice.customer),
                invoice.invoice_number,
                invoice.invoice_date,
                invoice.due_date,
                invoice.total_amount,
                invoice.amount_received,
                row["outstanding"],
                row["days_overdue"],
                invoice.status,
            ]
        )

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="townlit-ar-aging-{timezone.localdate()}.csv"'
    )
    return response


def customer_statement_export_view(request, customer_id):
    import csv
    from io import StringIO

    customer = get_object_or_404(Customer, pk=customer_id)
    events = []

    invoices = customer.invoices.filter(
        posting_journal_entry__isnull=False,
    ).order_by("invoice_date", "id")
    for invoice in invoices:
        events.append(
            {
                "date": invoice.invoice_date,
                "sort": 0,
                "type": "Invoice",
                "reference": invoice.invoice_number,
                "debit": invoice.total_amount,
                "credit": ZERO,
                "status": invoice.get_status_display(),
            }
        )

    allocations = CustomerReceiptAllocation.objects.filter(
        invoice__customer=customer,
    ).select_related("receipt", "invoice").order_by("receipt__receipt_date", "id")
    for allocation in allocations:
        events.append(
            {
                "date": allocation.receipt.receipt_date,
                "sort": 1,
                "type": "Receipt",
                "reference": allocation.receipt.reference,
                "debit": ZERO,
                "credit": allocation.amount,
                "status": f"Applied to {allocation.invoice.invoice_number}",
            }
        )

    events.sort(key=lambda item: (item["date"], item["sort"], item["reference"]))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Customer", str(customer)])
    writer.writerow(["Date", "Type", "Reference", "Debit", "Credit", "Balance", "Status"])

    balance = ZERO
    for event in events:
        balance += Decimal(str(event["debit"] or ZERO))
        balance -= Decimal(str(event["credit"] or ZERO))
        writer.writerow(
            [
                event["date"],
                event["type"],
                event["reference"],
                event["debit"],
                event["credit"],
                balance,
                event["status"],
            ]
        )

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    safe_code = customer.code.lower().replace(" ", "-")
    response["Content-Disposition"] = (
        f'attachment; filename="townlit-customer-statement-{safe_code}-{timezone.localdate()}.csv"'
    )
    return response


def invoice_print_view(request, invoice_id):
    invoice = get_object_or_404(
        CustomerInvoice.objects.select_related("customer", "receivable_account"),
        pk=invoice_id,
    )
    lines = invoice.lines.select_related("revenue_account", "tax_account", "fund").order_by(
        "line_number",
        "id",
    )
    return render(
        request,
        "admin/accounting/customer_invoice/print.html",
        {
            **accounting_admin_site.each_context(request),
            "title": f"Invoice {invoice.invoice_number}",
            "invoice": invoice,
            "lines": lines,
        },
    )
