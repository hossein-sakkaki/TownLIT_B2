# apps/accounting/models/bank_institution.py

from django.db import models


class BankInstitution(models.Model):
    """
    Represents a financial institution or payment processor.
    Example: TD, RBC, Stripe, PayPal.
    """

    TYPE_BANK = "bank"
    TYPE_CREDIT_UNION = "credit_union"
    TYPE_PAYMENT_PROCESSOR = "payment_processor"
    TYPE_FINTECH = "fintech"
    TYPE_OTHER = "other"

    INSTITUTION_TYPE_CHOICES = (
        (TYPE_BANK, "Bank"),
        (TYPE_CREDIT_UNION, "Credit Union"),
        (TYPE_PAYMENT_PROCESSOR, "Payment Processor"),
        (TYPE_FINTECH, "Fintech"),
        (TYPE_OTHER, "Other"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique institution code",
    )

    name = models.CharField(max_length=255)

    institution_type = models.CharField(
        max_length=30,
        choices=INSTITUTION_TYPE_CHOICES,
        default=TYPE_BANK,
        db_index=True,
    )

    country = models.CharField(
        max_length=2,
        default="CA",
        help_text="ISO country code",
    )

    swift_code = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    website = models.URLField(blank=True)

    support_phone = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    support_email = models.EmailField(blank=True)

    note = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Bank Institution"
        verbose_name_plural = "Bank Institutions"

    def __str__(self):
        return f"{self.code} - {self.name}"