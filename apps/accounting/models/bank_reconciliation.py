# apps/accounting/models/bank_reconciliation.py

from django.conf import settings
from django.db import models

from .bank import BankAccount
from .journal_entry import JournalEntry


class BankStatementImport(models.Model):
    """
    Represents one imported bank statement file or batch.
    """

    STATUS_IMPORTED = "imported"
    STATUS_PROCESSED = "processed"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = (
        (STATUS_IMPORTED, "Imported"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_ARCHIVED, "Archived"),
    )

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="statement_imports",
    )

    source_file = models.FileField(
        upload_to="accounting/bank_imports/%Y/%m/",
        null=True,
        blank=True,
    )

    file_name = models.CharField(max_length=255, blank=True)

    statement_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    opening_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    closing_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    currency = models.CharField(max_length=10, default="CAD")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IMPORTED,
        db_index=True,
    )

    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imported_bank_statements",
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.bank_account.code} | {self.file_name or self.id}"


class BankStatementLine(models.Model):
    """
    One transaction line imported from a bank statement.
    """

    MATCH_UNMATCHED = "unmatched"
    MATCH_SUGGESTED = "suggested"
    MATCH_MATCHED = "matched"
    MATCH_IGNORED = "ignored"

    MATCH_STATUS_CHOICES = (
        (MATCH_UNMATCHED, "Unmatched"),
        (MATCH_SUGGESTED, "Suggested"),
        (MATCH_MATCHED, "Matched"),
        (MATCH_IGNORED, "Ignored"),
    )

    statement_import = models.ForeignKey(
        BankStatementImport,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="statement_lines",
    )

    transaction_date = models.DateField(db_index=True)

    posted_date = models.DateField(null=True, blank=True)

    description = models.CharField(max_length=500)

    reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Signed amount. Positive inflow, negative outflow.",
    )

    balance_after = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    external_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Bank-provided transaction id if available",
    )

    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default=MATCH_UNMATCHED,
        db_index=True,
    )

    matched_journal_entry = models.ForeignKey(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matched_bank_lines",
    )

    matched_at = models.DateTimeField(null=True, blank=True)

    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matched_bank_statement_lines",
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("transaction_date", "id")
        indexes = [
            models.Index(fields=["bank_account", "transaction_date"]),
            models.Index(fields=["match_status", "transaction_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["statement_import", "external_id"],
                condition=models.Q(external_id__gt=""),
                name="uniq_statement_import_external_id",
            )
        ]

    def __str__(self):
        return f"{self.transaction_date} | {self.amount} | {self.description}"


class BankReconciliationSession(models.Model):
    """
    Represents a reconciliation session for one bank account and period.
    """

    STATUS_OPEN = "open"
    STATUS_COMPLETED = "completed"
    STATUS_LOCKED = "locked"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_LOCKED, "Locked"),
    )

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="reconciliation_sessions",
    )

    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)

    statement_ending_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    ledger_ending_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    unreconciled_difference = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )

    note = models.TextField(blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_reconciliation_sessions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_end", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "period_start", "period_end"],
                name="uniq_bank_reconciliation_period",
            )
        ]

    def __str__(self):
        return f"{self.bank_account.code} | {self.period_start} - {self.period_end}"