# apps/accounting/models/bank_reconciliation.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .bank import BankAccount
from .journal_entry import JournalEntry


ZERO = Decimal("0.00")


def _build_dedupe_key(parts: list[str]) -> str:
    payload = json.dumps(
        parts,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BankStatementImport(models.Model):
    """
    Represents one imported bank statement file or batch.
    """

    STATUS_IMPORTED = "imported"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = (
        (STATUS_IMPORTED, "Imported"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
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

    file_name = models.CharField(
        max_length=255,
        blank=True,
    )

    file_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        editable=False,
    )

    file_dedupe_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="Internal MySQL-safe file idempotency key",
    )

    statement_date = models.DateField(
        null=True,
        blank=True,
    )

    period_start = models.DateField(
        null=True,
        blank=True,
    )

    period_end = models.DateField(
        null=True,
        blank=True,
    )

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

    currency = models.CharField(
        max_length=10,
        default="CAD",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IMPORTED,
        db_index=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imported_bank_statements",
    )

    error_message = models.TextField(blank=True)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["bank_account", "status"]),
        ]

    def __str__(self):
        return f"{self.bank_account.code} | {self.file_name or self.id}"

    @classmethod
    def build_file_dedupe_key(
        cls,
        *,
        bank_account_id: int | None,
        file_hash: str | None,
    ) -> str | None:
        file_hash = (file_hash or "").strip().lower()

        if not bank_account_id or not file_hash:
            return None

        return _build_dedupe_key(
            [str(bank_account_id), file_hash]
        )

    def clean(self):
        super().clean()

        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                raise ValidationError(
                    {"period_end": "Period end cannot be before period start."}
                )

        if self.file_dedupe_key:
            expected_key = self.build_file_dedupe_key(
                bank_account_id=self.bank_account_id,
                file_hash=self.file_hash,
            )

            if not expected_key or self.file_dedupe_key != expected_key:
                raise ValidationError(
                    {"file_dedupe_key": "Invalid file dedupe key."}
                )

    def save(self, *args, **kwargs):
        if self._state.adding and self.file_hash:
            self.file_dedupe_key = self.build_file_dedupe_key(
                bank_account_id=self.bank_account_id,
                file_hash=self.file_hash,
            )

        elif self.file_dedupe_key:
            self.file_dedupe_key = self.build_file_dedupe_key(
                bank_account_id=self.bank_account_id,
                file_hash=self.file_hash,
            )

        self.full_clean()
        return super().save(*args, **kwargs)


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

    external_dedupe_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="Internal MySQL-safe bank transaction key",
    )

    fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        editable=False,
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
            models.Index(fields=["bank_account", "fingerprint"]),
        ]

    def __str__(self):
        return f"{self.transaction_date} | {self.amount} | {self.description}"

    @classmethod
    def build_external_dedupe_key(
        cls,
        *,
        bank_account_id: int | None,
        external_id: str | None,
    ) -> str | None:
        external_id = (external_id or "").strip()

        if not bank_account_id or not external_id:
            return None

        return _build_dedupe_key(
            [str(bank_account_id), external_id]
        )

    def clean(self):
        super().clean()

        if self.statement_import_id and self.bank_account_id:
            if self.statement_import.bank_account_id != self.bank_account_id:
                raise ValidationError(
                    {
                        "bank_account":
                            "Bank account must match the statement import."
                    }
                )

        if self.external_dedupe_key:
            expected_key = self.build_external_dedupe_key(
                bank_account_id=self.bank_account_id,
                external_id=self.external_id,
            )

            if not expected_key or self.external_dedupe_key != expected_key:
                raise ValidationError(
                    {"external_dedupe_key": "Invalid external dedupe key."}
                )

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.external_dedupe_key = self.build_external_dedupe_key(
                bank_account_id=self.bank_account_id,
                external_id=self.external_id,
            )

        elif self.external_dedupe_key:
            self.external_dedupe_key = self.build_external_dedupe_key(
                bank_account_id=self.bank_account_id,
                external_id=self.external_id,
            )

        self.full_clean()
        return super().save(*args, **kwargs)


class BankReconciliationSession(models.Model):
    """
    Represents one bank reconciliation period.
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

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_reconciliation_sessions",
    )

    locked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locked_bank_reconciliation_sessions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_end", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["bank_account", "period_start", "period_end"],
                name="uniq_bank_reconciliation_period",
            ),
            models.CheckConstraint(
                check=models.Q(period_end__gte=models.F("period_start")),
                name="bank_reconciliation_end_gte_start",
            ),
        ]

    def __str__(self):
        return f"{self.bank_account.code} | {self.period_start} - {self.period_end}"

    def clean(self):
        super().clean()

        if self.period_end < self.period_start:
            raise ValidationError(
                {"period_end": "Period end cannot be before period start."}
            )

        if self.status in (
            self.STATUS_COMPLETED,
            self.STATUS_LOCKED,
        ):
            difference = self.unreconciled_difference or ZERO

            if difference != ZERO:
                raise ValidationError(
                    {
                        "unreconciled_difference":
                            "Completed or locked reconciliation must balance to zero."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)