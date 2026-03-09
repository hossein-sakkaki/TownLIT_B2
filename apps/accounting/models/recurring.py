# apps/accounting/models/recurring.py

from django.conf import settings
from django.db import models


class RecurringJournalTemplate(models.Model):
    """
    Template for recurring accounting entries.
    Can be used for monthly hosting, rent allocation, subscriptions, etc.
    """

    FREQ_MONTHLY = "monthly"
    FREQ_QUARTERLY = "quarterly"
    FREQ_YEARLY = "yearly"

    FREQUENCY_CHOICES = (
        (FREQ_MONTHLY, "Monthly"),
        (FREQ_QUARTERLY, "Quarterly"),
        (FREQ_YEARLY, "Yearly"),
    )

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_CLOSED, "Closed"),
    )

    TEMPLATE_STANDARD = "standard"
    TEMPLATE_HOME_OFFICE = "home_office"
    TEMPLATE_FOUNDER_LOAN = "founder_loan"

    TEMPLATE_TYPE_CHOICES = (
        (TEMPLATE_STANDARD, "Standard"),
        (TEMPLATE_HOME_OFFICE, "Home Office"),
        (TEMPLATE_FOUNDER_LOAN, "Founder Loan"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    name = models.CharField(max_length=255)

    template_type = models.CharField(
        max_length=30,
        choices=TEMPLATE_TYPE_CHOICES,
        default=TEMPLATE_STANDARD,
        db_index=True,
    )

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQ_MONTHLY,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    description = models.TextField(blank=True)

    # Loose template payload for future flexibility
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Template configuration for recurring posting",
    )

    next_run_date = models.DateField(null=True, blank=True, db_index=True)
    last_run_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_recurring_journal_templates",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} - {self.name}"