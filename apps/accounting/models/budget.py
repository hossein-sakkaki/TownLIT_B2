# apps/accounting/models/budget.py

from django.db import models
from .fund import Fund


class Budget(models.Model):
    """
    Budget attached to a fund or internal program plan.
    """

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLOSED, "Closed"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique budget code",
    )

    name = models.CharField(max_length=255)

    fund = models.ForeignKey(
        Fund,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="budgets",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)

    currency = models.CharField(max_length=10, default="CAD")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} - {self.name}"


class BudgetLine(models.Model):
    """
    One approved budget line under a budget.
    """

    code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Unique code inside the budget scope",
    )

    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    name = models.CharField(max_length=255)

    description = models.TextField(blank=True)

    approved_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    is_active = models.BooleanField(default=True)

    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "code")
        constraints = [
            models.UniqueConstraint(
                fields=["budget", "code"],
                name="uniq_budget_line_code_per_budget",
            )
        ]

    def __str__(self):
        return f"{self.budget.code} / {self.code} - {self.name}"