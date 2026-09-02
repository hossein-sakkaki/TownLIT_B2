# apps/accounting/models/vendor_ap.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .account import Account
from .bank import BankAccount
from .budget import BudgetLine
from .fixed_asset import FixedAsset
from .fund import Fund
from .journal_entry import JournalEntry


ZERO = Decimal("0.00")


class Vendor(models.Model):
    """Supplier master used by Accounts Payable."""

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

    email = models.EmailField(blank=True, default="")
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
    tax_registration_number = models.CharField(max_length=100, blank=True, default="")
    account_number_with_vendor = models.CharField(max_length=100, blank=True, default="")

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

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        self.legal_name = (self.legal_name or "").strip()
        self.display_name = (self.display_name or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)


class VendorBill(models.Model):
    """Vendor invoice recognized into Accounts Payable."""

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
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="bills",
    )
    bill_number = models.CharField(max_length=120, db_index=True)
    bill_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    currency = models.CharField(max_length=10, default="CAD")

    description = models.CharField(max_length=255, blank=True, default="")
    internal_note = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

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
        related_name="vendor_bill",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="posted_vendor_bills",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_vendor_bills",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-bill_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "bill_number"],
                name="uniq_vendor_bill_number",
            ),
            models.CheckConstraint(
                check=Q(due_date__gte=models.F("bill_date")),
                name="vendor_bill_due_on_or_after_bill_date",
            ),
            models.CheckConstraint(
                check=Q(subtotal__gte=ZERO),
                name="vendor_bill_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(tax_total__gte=ZERO),
                name="vendor_bill_tax_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(total_amount__gte=ZERO),
                name="vendor_bill_total_nonnegative",
            ),
            models.CheckConstraint(
                check=Q(amount_paid__gte=ZERO),
                name="vendor_bill_paid_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["vendor", "status", "due_date"]),
            models.Index(fields=["bill_date", "status"]),
        ]

    def __str__(self):
        return f"{self.vendor} | {self.bill_number}"

    @property
    def outstanding_amount(self):
        return max((self.total_amount or ZERO) - (self.amount_paid or ZERO), ZERO)

    @property
    def is_posted(self):
        return bool(self.posting_journal_entry_id)

    def clean(self):
        if self.due_date and self.bill_date and self.due_date < self.bill_date:
            raise ValidationError({"due_date": "Due date cannot be before bill date."})
        if self.amount_paid and self.total_amount and self.amount_paid > self.total_amount:
            raise ValidationError({"amount_paid": "Paid amount cannot exceed bill total."})

    def save(self, *args, **kwargs):
        self.bill_number = (self.bill_number or "").strip()
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.posting_journal_entry_id:
                protected = (
                    "vendor_id",
                    "bill_number",
                    "bill_date",
                    "due_date",
                    "currency",
                    "description",
                )
                changed = [name for name in protected if getattr(original, name) != getattr(self, name)]
                if changed:
                    raise ValidationError(
                        "Posted vendor bills are immutable. Reverse/correct them through accounting workflow."
                    )
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.posting_journal_entry_id:
            raise ValidationError("Posted vendor bills cannot be deleted.")
        return super().delete(*args, **kwargs)


class VendorBillLine(models.Model):
    """One expense, prepaid or capital line on a vendor bill."""

    bill = models.ForeignKey(
        VendorBill,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_number = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255)
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="vendor_bill_lines",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Amount before separately recoverable tax.",
    )
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_account = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vendor_bill_tax_lines",
        help_text="Optional recoverable-tax asset account. Leave blank when tax is part of expense/asset cost.",
    )

    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vendor_bill_lines",
    )
    budget_line = models.ForeignKey(
        BudgetLine,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vendor_bill_lines",
    )

    capitalize_as_fixed_asset = models.BooleanField(default=False)
    fixed_asset = models.OneToOneField(
        FixedAsset,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vendor_bill_line",
    )
    asset_name = models.CharField(max_length=255, blank=True, default="")
    placed_in_service_date = models.DateField(null=True, blank=True)
    useful_life_months = models.PositiveIntegerField(null=True, blank=True)
    salvage_value = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    serial_number = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("line_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["bill", "line_number"],
                name="uniq_vendor_bill_line_number",
            ),
            models.CheckConstraint(
                check=Q(amount__gt=ZERO),
                name="vendor_bill_line_amount_positive",
            ),
            models.CheckConstraint(
                check=Q(tax_amount__gte=ZERO),
                name="vendor_bill_line_tax_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.bill.bill_number} / {self.line_number}"

    @property
    def gross_amount(self):
        return (self.amount or ZERO) + (self.tax_amount or ZERO)

    @property
    def primary_posting_amount(self):
        if self.tax_amount and self.tax_account_id:
            return self.amount or ZERO
        return self.gross_amount

    def clean(self):
        if self.account_id:
            if self.account.account_type not in {Account.TYPE_EXPENSE, Account.TYPE_ASSET}:
                raise ValidationError({"account": "Vendor bill lines must use an expense or asset account."})
            if not self.account.is_active or not self.account.allows_posting:
                raise ValidationError({"account": "Account must be active and postable."})

        if self.tax_account_id:
            if not self.tax_amount or self.tax_amount <= ZERO:
                raise ValidationError({"tax_account": "A tax account requires a positive tax amount."})
            if self.tax_account.account_type != Account.TYPE_ASSET:
                raise ValidationError({"tax_account": "Recoverable tax must use an asset account."})
            if self.tax_account.parent_id is None or self.tax_account.parent.code != "1400":
                raise ValidationError({"tax_account": "Recoverable tax must use an account under Recoverable Taxes (1400)."})
            if not self.tax_account.is_active or not self.tax_account.allows_posting:
                raise ValidationError({"tax_account": "Tax account must be active and postable."})

        if self.budget_line_id:
            budget_fund_id = self.budget_line.budget.fund_id
            if budget_fund_id and (not self.fund_id or budget_fund_id != self.fund_id):
                raise ValidationError({"budget_line": "Budget line must belong to the selected fund."})

        if self.capitalize_as_fixed_asset:
            if not self.account_id or self.account.account_type != Account.TYPE_ASSET:
                raise ValidationError({"account": "Capitalized bill lines must use an asset account."})
            if not self.asset_name.strip():
                raise ValidationError({"asset_name": "Capitalized bill lines require an asset name."})
            if not self.placed_in_service_date:
                raise ValidationError({"placed_in_service_date": "Placed-in-service date is required."})
            if not self.useful_life_months:
                raise ValidationError({"useful_life_months": "Useful life is required."})
            capitalized_cost = self.primary_posting_amount
            if self.salvage_value < ZERO or self.salvage_value >= capitalized_cost:
                raise ValidationError({"salvage_value": "Salvage value must be non-negative and below capitalized cost."})

    def save(self, *args, **kwargs):
        if self.bill_id and self.bill.posting_journal_entry_id:
            raise ValidationError("Lines on a posted vendor bill cannot be changed.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.bill_id and self.bill.posting_journal_entry_id:
            raise ValidationError("Lines on a posted vendor bill cannot be deleted.")
        return super().delete(*args, **kwargs)


class VendorPayment(models.Model):
    """One actual payment to a vendor, optionally allocated across bills."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payment_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="payments")
    payment_date = models.DateField(db_index=True)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="vendor_payments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default="CAD")
    payment_method = models.CharField(
        max_length=30,
        choices=Vendor.PAYMENT_METHOD_CHOICES,
        default=Vendor.METHOD_EFT,
    )
    reference = models.CharField(max_length=255, db_index=True)
    note = models.TextField(blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="vendor_payment",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_vendor_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-payment_date", "-id")
        indexes = [
            models.Index(fields=["vendor", "payment_date"]),
            models.Index(fields=["bank_account", "payment_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gt=ZERO),
                name="vendor_payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["vendor", "reference"],
                name="uniq_vendor_payment_reference",
            ),
        ]

    def __str__(self):
        return f"{self.payment_number} | {self.vendor} | {self.amount}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = f"VP-{str(self.public_id).split('-')[0].upper()}"
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original:
                protected = (
                    "vendor_id", "payment_date", "bank_account_id", "amount", "currency",
                    "payment_method", "reference", "journal_entry_id",
                )
                if any(getattr(original, name) != getattr(self, name) for name in protected):
                    raise ValidationError("Posted vendor payments are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted vendor payments cannot be deleted.")


class VendorPaymentAllocation(models.Model):
    """Allocation of one vendor payment to one bill."""

    payment = models.ForeignKey(
        VendorPayment,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    bill = models.ForeignKey(
        VendorBill,
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("bill__due_date", "bill_id")
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "bill"],
                name="uniq_vendor_payment_bill_allocation",
            ),
            models.CheckConstraint(
                check=Q(amount__gt=ZERO),
                name="vendor_payment_allocation_positive",
            ),
        ]

    def __str__(self):
        return f"{self.payment.payment_number} -> {self.bill.bill_number}"

    def clean(self):
        if self.payment_id and self.bill_id and self.payment.vendor_id != self.bill.vendor_id:
            raise ValidationError("Payment and bill must belong to the same vendor.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Vendor payment allocations are immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Vendor payment allocations cannot be deleted.")


class VendorAPAttachment(models.Model):
    """Invoice or payment evidence kept beside the AP workflow."""

    TYPE_INVOICE = "invoice"
    TYPE_PAYMENT_PROOF = "payment_proof"
    TYPE_CREDIT_NOTE = "credit_note"
    TYPE_OTHER = "other"

    TYPE_CHOICES = (
        (TYPE_INVOICE, "Invoice"),
        (TYPE_PAYMENT_PROOF, "Payment Proof"),
        (TYPE_CREDIT_NOTE, "Credit Note"),
        (TYPE_OTHER, "Other"),
    )

    bill = models.ForeignKey(
        VendorBill,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    payment = models.ForeignKey(
        VendorPayment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_OTHER)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="accounting/ap/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_vendor_ap_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                check=(Q(bill__isnull=False, payment__isnull=True) | Q(bill__isnull=True, payment__isnull=False)),
                name="vendor_ap_attachment_exactly_one_parent",
            ),
        ]

    def __str__(self):
        return self.title
