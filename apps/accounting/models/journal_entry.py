# apps/accounting/models/journal_entry.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import hashlib
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class JournalEntry(models.Model):
    """
    Represents a financial journal entry.
    """

    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_VOID = "void"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_POSTED, "Posted"),
        (STATUS_VOID, "Void"),
    )

    IMMUTABLE_POSTED_FIELDS = (
        "entry_number",
        "entry_date",
        "description",
        "reference",
        "source_app",
        "source_model",
        "source_ref",
        "source_dedupe_key",
        "status",
        "currency",
        "internal_note",
        "posted_at",
        "voided_at",
        "void_reason",
        "created_by_id",
        "approved_by_id",
        "reversal_of_id",
    )

    entry_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Human-friendly unique entry number",
    )

    entry_date = models.DateField(db_index=True)
    description = models.TextField()

    reference = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="External business reference such as invoice id",
    )

    source_app = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    source_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    source_ref = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    source_dedupe_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="Internal MySQL-safe source idempotency key",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )

    currency = models.CharField(
        max_length=10,
        default="CAD",
        db_index=True,
    )

    internal_note = models.TextField(blank=True)

    posted_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

    reversal_of = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal_entry",
    )

    reversed_at = models.DateTimeField(null=True, blank=True)

    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_journal_entries",
    )

    reversal_reason = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_journal_entries",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_journal_entries",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-entry_date", "-id")
        indexes = [
            models.Index(fields=["entry_date", "status"]),
            models.Index(fields=["source_app", "source_model", "source_ref"]),
            models.Index(fields=["reference", "status"]),
        ]

    def __str__(self):
        return f"{self.entry_number} | {self.entry_date} | {self.status}"

    @classmethod
    def build_source_dedupe_key(
        cls,
        *,
        source_app: str | None,
        source_model: str | None,
        source_ref: str | None,
    ) -> str | None:
        """
        Build a stable source identity key.
        """

        source_app = (source_app or "").strip()
        source_model = (source_model or "").strip()
        source_ref = (source_ref or "").strip()

        if not source_app or not source_model or not source_ref:
            return None

        payload = json.dumps(
            [source_app, source_model, source_ref],
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def clean(self):
        super().clean()

        if self.source_dedupe_key:
            expected_key = self.build_source_dedupe_key(
                source_app=self.source_app,
                source_model=self.source_model,
                source_ref=self.source_ref,
            )

            if not expected_key or self.source_dedupe_key != expected_key:
                raise ValidationError(
                    {"source_dedupe_key": "Invalid source dedupe key."}
                )

        if self.reversal_of_id:
            if self.pk and self.reversal_of_id == self.pk:
                raise ValidationError(
                    {"reversal_of": "A journal entry cannot reverse itself."}
                )

            if self.reversal_of.status != self.STATUS_POSTED:
                raise ValidationError(
                    {"reversal_of": "Only posted journal entries can be reversed."}
                )

    def save(self, *args, **kwargs):
        self.source_app = (self.source_app or "").strip()
        self.source_model = (self.source_model or "").strip()
        self.source_ref = (self.source_ref or "").strip()

        is_new = self._state.adding
        original = None

        if not is_new and self.pk:
            original = type(self).objects.get(pk=self.pk)

        if is_new:
            if self.status == self.STATUS_POSTED:
                if not getattr(self, "_allow_posted_create", False):
                    raise ValidationError(
                        "Posted journal entries must be created through PostingEngine."
                    )

            self.source_dedupe_key = self.build_source_dedupe_key(
                source_app=self.source_app,
                source_model=self.source_model,
                source_ref=self.source_ref,
            )

        elif original.status == self.STATUS_POSTED:
            changed_fields = [
                field
                for field in self.IMMUTABLE_POSTED_FIELDS
                if getattr(original, field) != getattr(self, field)
            ]

            if changed_fields:
                raise ValidationError(
                    "Posted journal entries are immutable. "
                    f"Changed fields: {', '.join(changed_fields)}."
                )

        else:
            if self.status == self.STATUS_POSTED:
                if not getattr(self, "_allow_posted_transition", False):
                    raise ValidationError(
                        "Draft journal entries must be posted through PostingEngine."
                    )

            self.source_dedupe_key = self.build_source_dedupe_key(
                source_app=self.source_app,
                source_model=self.source_model,
                source_ref=self.source_ref,
            )

        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.STATUS_POSTED:
            raise ValidationError(
                "Posted journal entries cannot be deleted. Use a reversal."
            )

        return super().delete(*args, **kwargs)