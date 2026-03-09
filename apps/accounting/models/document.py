# apps/accounting/models/document.py

from django.conf import settings
from django.db import models

from .journal_entry import JournalEntry
from .fund import Fund
from .founder_loan import FounderLoan


class AccountingDocument(models.Model):
    """
    Stores accounting-related documents for audit and archive purposes.
    """

    TYPE_INVOICE = "invoice"
    TYPE_RECEIPT = "receipt"
    TYPE_CONTRACT = "contract"
    TYPE_GRANT_LETTER = "grant_letter"
    TYPE_PAYMENT_PROOF = "payment_proof"
    TYPE_BANK_SUPPORT = "bank_support"
    TYPE_OTHER = "other"

    DOCUMENT_TYPE_CHOICES = (
        (TYPE_INVOICE, "Invoice"),
        (TYPE_RECEIPT, "Receipt"),
        (TYPE_CONTRACT, "Contract"),
        (TYPE_GRANT_LETTER, "Grant Letter"),
        (TYPE_PAYMENT_PROOF, "Payment Proof"),
        (TYPE_BANK_SUPPORT, "Bank Support"),
        (TYPE_OTHER, "Other"),
    )

    title = models.CharField(max_length=255)

    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        default=TYPE_OTHER,
        db_index=True,
    )

    file = models.FileField(
        upload_to="accounting/documents/%Y/%m/",
    )

    description = models.TextField(blank=True)

    # Optional direct links
    journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )

    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )

    founder_loan = models.ForeignKey(
        FounderLoan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )

    reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Invoice number, receipt number, or external reference",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_accounting_documents",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["document_type", "reference"]),
        ]

    def __str__(self):
        return self.title