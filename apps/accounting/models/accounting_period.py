# apps/accounting/models/accounting_period.py

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class AccountingPeriod(models.Model):
    """
    Represents a controllable accounting period.
    Designed for month-end close and lock workflow.
    """

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_LOCKED = "locked"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_LOCKED, "Locked"),
    )

    PERIOD_TYPE_MONTH = "month"
    PERIOD_TYPE_YEAR = "year"

    PERIOD_TYPE_CHOICES = (
        (PERIOD_TYPE_MONTH, "Month"),
        (PERIOD_TYPE_YEAR, "Year"),
    )

    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Example: FY2026-06 or FY2026",
    )

    name = models.CharField(
        max_length=100,
        help_text="Human-readable period name",
    )

    fiscal_year_label = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Example: FY2026",
    )

    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPE_CHOICES,
        default=PERIOD_TYPE_MONTH,
        db_index=True,
    )

    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )

    note = models.TextField(blank=True)

    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_accounting_periods",
    )

    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locked_accounting_periods",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("start_date",)
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="accounting_period_end_gte_start",
            ),
        ]

    def __str__(self):
        return f"{self.code} ({self.start_date} → {self.end_date})"

    def clean(self):
        """
        Validate period dates and uniqueness logic.
        """

        super().clean()

        if self.end_date < self.start_date:
            raise ValidationError("end_date cannot be earlier than start_date.")