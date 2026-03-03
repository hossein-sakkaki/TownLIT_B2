# apps/advancement/models/commitment.py

from django.db import models
import uuid
from .opportunity import Opportunity
from decimal import Decimal, ROUND_HALF_UP


class Commitment(models.Model):
    """
    Represents a pledged or approved funding commitment.
    This model does NOT manage transactions or accounting entries.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = (
        ("PLEDGED", "Pledged"),
        ("CONFIRMED", "Confirmed"),
        ("CONDITIONAL", "Conditional"),
        ("FULFILLED", "Fulfilled"),
        ("CANCELLED", "Cancelled"),
    )

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="commitments"
    )

    # Original committed amount
    committed_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    currency = models.CharField(max_length=3)  # ISO currency

    base_currency_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Exchange rate snapshot at time of commitment
    exchange_rate_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("1.0")
    )

    commitment_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PLEDGED"
    )

    conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-commitment_date"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["currency"]),
        ]

    def __str__(self):
        return f"{self.opportunity.title} - {self.committed_amount} {self.currency}"

    def save(self, *args, **kwargs):
        """Auto-calc base_currency_amount when missing."""
        if self.base_currency_amount is None:
            rate = self.exchange_rate_snapshot or Decimal("1.0")
            value = (self.committed_amount or Decimal("0.00")) * rate

            # Keep consistent with decimal_places=2
            self.base_currency_amount = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)