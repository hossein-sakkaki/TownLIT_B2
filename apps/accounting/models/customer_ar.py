# apps/accounting/models/customer_ar.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal, ROUND_HALF_UP
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .account import Account
from .bank import BankAccount
from .fund import Fund
from .journal_entry import JournalEntry


ZERO = Decimal("0.00")
MONEY_QUANTUM = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class Customer(models.Model):
    """Customer master used by Accounts Receivable."""

    METHOD_E_TRANSFER = "e_transfer"
    METHOD_EFT = "eft"
    METHOD_CHEQUE = "cheque"
    METHOD_CARD = "card"
    METHOD_WIRE = "wire"
    METHOD_OTHER = "other"

    PAYMENT_METHOD_CHOICES = (
        (METHOD_E_TRANSFER, "E-Transfer"),
        (METHOD_EFT, "EFT / Direct Deposit"),
        (METHOD_CHEQUE, "Cheque"),
        (METHOD_CARD, "Card"),
        (METHOD_WIRE, "Wire Transfer"),
        (METHOD_OTHER, "Other"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    legal_name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True, default="")

    billing_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    website = models.URLField(blank=True, default="")

    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    province = models.CharField(max_length=120, blank=True, default="")
    postal_code = models.CharField(max_length=30, blank=True, default="")
    country = models.CharField(max_length=2, default="CA")

    default_terms_days = models.PositiveSmallIntegerField(default=30)
    default_payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        default=METHOD_EFT,
    )
    default_receivable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="customer_default_receivable_accounts",
        help_text="Posting account under Accounts Receivable (1100).",
    )
    default_revenue_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_default_revenue_accounts",
    )

    tax_registration_number = models.CharField(max_length=100, blank=True, default="")
    customer_reference = models.CharField(max_length=100, blank=True, default="")
    internal_note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_name", "legal_name", "code")
        indexes = [
            models.Index(fields=["is_active", "legal_name"]),
        ]

    def __str__(self):
        return self.display_name or self.legal_name

    def clean(self):
        if self.default_receivable_account_id:
            account = self.default_receivable_account
            if account.account_type != Account.TYPE_ASSET:
                raise ValidationError({"default_receivable_account": "Receivable account must be an asset account."})
            if not account.is_active or not account.allows_posting:
                raise ValidationError({"default_receivable_account": "Receivable account must be active and postable."})
            if not account.parent_id or account.parent.code != "1100":
                raise ValidationError({
                    "default_receivable_account": "Receivable account must be a posting account under Accounts Receivable (1100)."
                })

        if self.default_revenue_account_id:
            account = self.default_revenue_account
            if account.account_type != Account.TYPE_REVENUE:
                raise ValidationError({"default_revenue_account": "Default revenue account must be a revenue account."})
            if not account.is_active or not account.allows_posting:
                raise ValidationError({"default_revenue_account": "Default revenue account must be active and postable."})

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        self.legal_name = (self.legal_name or "").strip()
        self.display_name = (self.display_name or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)


class CustomerInvoice(models.Model):
    """TownLIT invoice recognized into Accounts Receivable."""

    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_VOID = "void"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_OPEN, "Open"),
        (STATUS_PARTIAL, "Partially Paid"),
        (STATUS_PAID, "Paid"),
        (STATUS_VOID, "Void"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    invoice_number = models.CharField(
        max_length=120,
        unique=True,
        db_index=True,
        blank=True,
        default="",
        help_text="Leave blank to generate a TownLIT invoice number automatically.",
    )
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    receivable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="customer_invoices",
    )
    currency = models.CharField(max_length=10, default="CAD")

    description = models.CharField(max_length=255, blank=True, default="")
    purchase_order_reference = models.CharField(max_length=120, blank=True, default="")
    internal_note = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    amount_received = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )

    posting_journal_entry = models.OneToOneField(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_invoice",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posted_customer_invoices",
    )
    sent_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_customer_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-invoice_date", "-id")
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["customer", "status", "due_date"]),
            models.Index(fields=["invoice_date", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(due_date__gte=models.F("invoice_date")),
                name="customer_invoice_due_on_or_after_invoice_date",
            ),
            models.CheckConstraint(
                check=Q(subtotal__gte=ZERO),
                name="customer_invoice_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(tax_total__gte=ZERO),
                name="customer_invoice_tax_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(total_amount__gte=ZERO),
                name="customer_invoice_total_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(amount_received__gte=ZERO),
                name="customer_invoice_received_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(amount_received__lte=models.F("total_amount")),
                name="customer_invoice_received_not_over_total",
            ),
        ]

    def __str__(self):
        return f"{self.invoice_number or 'Draft'} | {self.customer}"

    @property
    def outstanding_amount(self):
        return max((self.total_amount or ZERO) - (self.amount_received or ZERO), ZERO)

    @property
    def is_posted(self):
        return bool(self.posting_journal_entry_id)

    def clean(self):
        if self.due_date and self.invoice_date and self.due_date < self.invoice_date:
            raise ValidationError({"due_date": "Due date cannot be before invoice date."})
        if self.amount_received and self.total_amount and self.amount_received > self.total_amount:
            raise ValidationError({"amount_received": "Received amount cannot exceed invoice total."})

        if self.receivable_account_id:
            account = self.receivable_account
            if account.account_type != Account.TYPE_ASSET:
                raise ValidationError({"receivable_account": "Receivable account must be an asset account."})
            if not account.is_active or not account.allows_posting:
                raise ValidationError({"receivable_account": "Receivable account must be active and postable."})
            if not account.parent_id or account.parent.code != "1100":
                raise ValidationError({
                    "receivable_account": "Receivable account must be a posting account under Accounts Receivable (1100)."
                })

    def save(self, *args, **kwargs):
        self.invoice_number = (self.invoice_number or "").strip().upper()
        if not self.invoice_number:
            date_part = self.invoice_date.strftime("%Y%m%d") if self.invoice_date else "UNDATED"
            self.invoice_number = f"INV-{date_part}-{str(self.public_id).split('-')[0].upper()}"

        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.posting_journal_entry_id:
                protected = (
                    "customer_id",
                    "invoice_number",
                    "invoice_date",
                    "due_date",
                    "receivable_account_id",
                    "currency",
                    "description",
                    "purchase_order_reference",
                )
                changed = [name for name in protected if getattr(original, name) != getattr(self, name)]
                if changed:
                    raise ValidationError(
                        "Posted customer invoices are immutable. Reverse/correct them through accounting workflow."
                    )

        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.posting_journal_entry_id:
            raise ValidationError("Posted customer invoices cannot be deleted.")
        return super().delete(*args, **kwargs)


class CustomerInvoiceLine(models.Model):
    """One revenue line on a customer invoice."""

    invoice = models.ForeignKey(
        CustomerInvoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_number = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("1.000"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)

    revenue_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="customer_invoice_revenue_lines",
    )
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_invoice_tax_lines",
        help_text="Sales-tax liability account. Required when tax amount is greater than zero.",
    )
    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="customer_invoice_lines",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("line_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "line_number"],
                name="uniq_customer_invoice_line_number",
            ),
            models.CheckConstraint(
                check=Q(quantity__gt=ZERO),
                name="customer_invoice_line_quantity_positive",
            ),
            models.CheckConstraint(
                check=Q(unit_price__gte=ZERO),
                name="customer_invoice_line_unit_price_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(amount__gte=ZERO),
                name="customer_invoice_line_amount_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(tax_amount__gte=ZERO),
                name="customer_invoice_line_tax_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} / {self.line_number}"

    @property
    def gross_amount(self):
        return (self.amount or ZERO) + (self.tax_amount or ZERO)

    def clean(self):
        calculated = _money(Decimal(str(self.quantity or ZERO)) * Decimal(str(self.unit_price or ZERO)))
        self.amount = calculated

        if self.revenue_account_id:
            account = self.revenue_account
            if account.account_type != Account.TYPE_REVENUE:
                raise ValidationError({"revenue_account": "Invoice lines must use a revenue account."})
            if not account.is_active or not account.allows_posting:
                raise ValidationError({"revenue_account": "Revenue account must be active and postable."})

        if self.tax_amount and self.tax_amount > ZERO:
            if not self.tax_account_id:
                raise ValidationError({"tax_account": "Select Sales Tax Payable when tax is charged."})
            if self.tax_account.code != "2310":
                raise ValidationError({"tax_account": "Sales tax must use Sales Tax Payable (2310)."})
            if self.tax_account.account_type != Account.TYPE_LIABILITY:
                raise ValidationError({"tax_account": "Sales tax account must be a liability account."})
            if not self.tax_account.is_active or not self.tax_account.allows_posting:
                raise ValidationError({"tax_account": "Sales tax account must be active and postable."})
        elif self.tax_account_id:
            raise ValidationError({"tax_account": "Remove the tax account when tax amount is zero."})

        if self.fund_id:
            if not self.fund.is_active or self.fund.status != self.fund.STATUS_ACTIVE:
                raise ValidationError({"fund": "Fund must be active for posting."})

    def save(self, *args, **kwargs):
        if self.invoice_id and self.invoice.posting_journal_entry_id:
            raise ValidationError("Lines on a posted customer invoice cannot be changed.")
        self.amount = _money(Decimal(str(self.quantity or ZERO)) * Decimal(str(self.unit_price or ZERO)))
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.invoice_id and self.invoice.posting_journal_entry_id:
            raise ValidationError("Lines on a posted customer invoice cannot be deleted.")
        return super().delete(*args, **kwargs)


class CustomerReceipt(models.Model):
    """One actual bank receipt from a customer."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="receipts")
    receipt_date = models.DateField(db_index=True)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="customer_receipts",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="CAD")
    payment_method = models.CharField(
        max_length=30,
        choices=Customer.PAYMENT_METHOD_CHOICES,
        default=Customer.METHOD_EFT,
    )
    reference = models.CharField(max_length=255, db_index=True)
    note = models.TextField(blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="customer_receipt",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_customer_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-receipt_date", "-id")
        indexes = [
            models.Index(fields=["customer", "receipt_date"]),
            models.Index(fields=["bank_account", "receipt_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gt=ZERO),
                name="customer_receipt_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["customer", "reference"],
                name="uniq_customer_receipt_reference",
            ),
        ]

    def __str__(self):
        return f"{self.receipt_number} | {self.customer} | {self.amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"CR-{str(self.public_id).split('-')[0].upper()}"
        self.reference = (self.reference or "").strip()
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original:
                protected = (
                    "customer_id",
                    "receipt_date",
                    "bank_account_id",
                    "amount",
                    "currency",
                    "payment_method",
                    "reference",
                    "journal_entry_id",
                )
                if any(getattr(original, name) != getattr(self, name) for name in protected):
                    raise ValidationError("Posted customer receipts are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted customer receipts cannot be deleted.")


class CustomerReceiptAllocation(models.Model):
    """Allocation of one customer receipt to one invoice."""

    receipt = models.ForeignKey(
        CustomerReceipt,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    invoice = models.ForeignKey(
        CustomerInvoice,
        on_delete=models.PROTECT,
        related_name="receipt_allocations",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("invoice__due_date", "invoice_id")
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "invoice"],
                name="uniq_customer_receipt_invoice_allocation",
            ),
            models.CheckConstraint(
                check=Q(amount__gt=ZERO),
                name="customer_receipt_allocation_positive",
            ),
        ]

    def __str__(self):
        return f"{self.receipt.receipt_number} -> {self.invoice.invoice_number}"

    def clean(self):
        if self.receipt_id and self.invoice_id and self.receipt.customer_id != self.invoice.customer_id:
            raise ValidationError("Receipt and invoice must belong to the same customer.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Customer receipt allocations are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Customer receipt allocations cannot be deleted.")


class CustomerARAttachment(models.Model):
    """Invoice or receipt evidence kept beside the AR workflow."""

    TYPE_INVOICE = "invoice"
    TYPE_RECEIPT_PROOF = "receipt_proof"
    TYPE_PURCHASE_ORDER = "purchase_order"
    TYPE_CONTRACT = "contract"
    TYPE_OTHER = "other"

    TYPE_CHOICES = (
        (TYPE_INVOICE, "Invoice"),
        (TYPE_RECEIPT_PROOF, "Receipt Proof"),
        (TYPE_PURCHASE_ORDER, "Purchase Order"),
        (TYPE_CONTRACT, "Contract"),
        (TYPE_OTHER, "Other"),
    )

    invoice = models.ForeignKey(
        CustomerInvoice,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    receipt = models.ForeignKey(
        CustomerReceipt,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_OTHER)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="accounting/ar/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_customer_ar_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(invoice__isnull=False, receipt__isnull=True)
                    | Q(invoice__isnull=True, receipt__isnull=False)
                ),
                name="customer_ar_attachment_exactly_one_parent",
            ),
        ]

    def __str__(self):
        return self.title
