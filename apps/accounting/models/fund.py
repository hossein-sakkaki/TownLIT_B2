# apps/accounting/models/fund.py

from django.db import models


class Fund(models.Model):
    """
    Represents a financial fund used for restricted or unrestricted accounting.
    A fund can represent a grant, donor-restricted support, or a general fund.
    """

    TYPE_GENERAL = "general"
    TYPE_RESTRICTED = "restricted"
    TYPE_GRANT = "grant"
    TYPE_SUPPORT = "support"

    FUND_TYPE_CHOICES = (
        (TYPE_GENERAL, "General"),
        (TYPE_RESTRICTED, "Restricted"),
        (TYPE_GRANT, "Grant"),
        (TYPE_SUPPORT, "Support"),
    )

    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_ON_HOLD = "on_hold"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_ON_HOLD, "On Hold"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique fund code",
    )

    name = models.CharField(max_length=255)

    fund_type = models.CharField(
        max_length=20,
        choices=FUND_TYPE_CHOICES,
        default=TYPE_GENERAL,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    description = models.TextField(blank=True)

    # Whether the fund is legally/contractually restricted
    is_restricted = models.BooleanField(default=False)

    # Loose reference to external domain such as advancement
    source_app = models.CharField(max_length=100, blank=True, default="")
    source_model = models.CharField(max_length=100, blank=True, default="")
    source_ref = models.CharField(max_length=255, blank=True, default="", db_index=True)

    # Funding period
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Optional approved funding amount
    total_awarded = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    currency = models.CharField(max_length=10, default="CAD")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        indexes = [
            models.Index(fields=["fund_type", "status"]),
            models.Index(fields=["source_app", "source_model", "source_ref"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"