# apps/accounting/models/accounting_period.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AccountingPeriod(models.Model):
    """Represents a controllable accounting period."""

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

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closed_accounting_periods",
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
        related_name="locked_accounting_periods",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ("start_date",)
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    end_date__gte=models.F("start_date")
                ),
                name="accounting_period_end_gte_start",
            ),
        ]

    def __str__(self):
        return (
            f"{self.code} "
            f"({self.start_date} → {self.end_date})"
        )

    def clean(self):
        """Validate period boundaries."""

        super().clean()

        if self.end_date < self.start_date:
            raise ValidationError(
                "end_date cannot be earlier than start_date."
            )

        if self.period_type != self.PERIOD_TYPE_MONTH:
            return

        overlaps = (
            type(self).objects
            .filter(
                period_type=self.PERIOD_TYPE_MONTH,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            )
        )

        if self.pk:
            overlaps = overlaps.exclude(pk=self.pk)

        conflicting = overlaps.order_by(
            "start_date",
            "id",
        ).first()

        if conflicting:
            raise ValidationError(
                "Monthly accounting periods cannot overlap. "
                f"Conflicting period: {conflicting.code}."
            )

    def save(self, *args, **kwargs):
        """Validate before persistence."""

        self.full_clean()

        return super().save(*args, **kwargs)