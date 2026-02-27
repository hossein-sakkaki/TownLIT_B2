# apps/advancement/models/external_entity.py

from django.db import models
import uuid


class ExternalEntity(models.Model):
    """
    Represents any external organization or donor interacting with TownLIT.
    Service-ready: fully isolated from core apps.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ENTITY_TYPE_CHOICES = (
        ("CHURCH", "Church"),
        ("FOUNDATION", "Foundation"),
        ("GOVERNMENT", "Government"),
        ("MISSION", "Mission Agency"),
        ("DONOR", "Major Donor"),
        ("NETWORK", "Network"),
    )

    # Core identity
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)

    # Geographic data (multi-country ready)
    country = models.CharField(max_length=2)  # ISO country code (CA, US, etc.)
    region = models.CharField(max_length=100, blank=True)

    # Faith/network metadata
    denomination = models.CharField(max_length=150, blank=True)

    # Contact data
    primary_email = models.EmailField(blank=True)
    primary_phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    # Web presence
    website = models.URLField(blank=True)

    # Classification
    tags = models.ManyToManyField(
        "advancement.Tag",
        blank=True,
        related_name="external_entities"
    )

    # Internal notes
    description = models.TextField(blank=True)
    notes_private = models.TextField(blank=True)

    # Status control
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["entity_type"]),
            models.Index(fields=["country"]),
        ]

    def __str__(self):
        return self.name