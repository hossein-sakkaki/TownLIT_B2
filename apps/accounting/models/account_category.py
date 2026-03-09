# apps/accounting/models/account_category.py

from django.db import models


class AccountCategory(models.Model):
    """
    High-level classification for accounts.
    Example: Assets, Liabilities, Equity, Revenue, Expenses.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    code_prefix = models.CharField(
        max_length=10,
        unique=True,
        help_text="Prefix used for account numbering",
    )

    description = models.TextField(blank=True)

    # Soft enable/disable for future flexibility
    is_active = models.BooleanField(default=True)

    # Optional display order
    sort_order = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Account Category"
        verbose_name_plural = "Account Categories"
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name