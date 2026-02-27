# apps/advancement/models/legal_entity.py

from django.db import models
import uuid


class LegalEntity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    COUNTRY_CHOICES = (
        ("CA", "Canada"),
        ("US", "United States"),
    )

    LEGAL_TYPE_CHOICES = (
        ("CA_CHARITY", "Canadian Registered Charity"),
        ("US_501C3", "US 501(c)(3)"),
        ("NONPROFIT", "Nonprofit Organization"),
    )

    name = models.CharField(max_length=255)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    legal_type = models.CharField(max_length=20, choices=LEGAL_TYPE_CHOICES)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    base_currency = models.CharField(max_length=3, default="CAD")
    active = models.BooleanField(default=True)
    effective_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name