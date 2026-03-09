# apps/accounting/models/journal_entry.py

from django.conf import settings
from django.db import models


class JournalEntry(models.Model):
    """
    Represents a financial journal entry.
    A journal entry contains multiple debit/credit transactions.
    """

    STATUS_DRAFT = "draft"
    STATUS_POSTED = "posted"
    STATUS_VOID = "void"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_POSTED, "Posted"),
        (STATUS_VOID, "Void"),
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

    # Loose source linkage for integration
    source_app = models.CharField(max_length=100, blank=True, default="")
    source_model = models.CharField(max_length=100, blank=True, default="")
    source_ref = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )

    # Basic currency support for future expansion
    currency = models.CharField(
        max_length=10,
        default="CAD",
        db_index=True,
    )

    internal_note = models.TextField(blank=True)

    posted_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)

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
        constraints = [
            models.UniqueConstraint(
                fields=["source_app", "source_model", "source_ref", "status"],
                condition=models.Q(
                    source_app__gt="",
                    source_model__gt="",
                    source_ref__gt="",
                    status="posted",
                ),
                name="uniq_posted_source_reference",
            )
        ]

    def __str__(self):
        return f"{self.entry_number} | {self.entry_date} | {self.status}"