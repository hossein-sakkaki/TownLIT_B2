# apps/advancement/models/opportunity.py

from django.db import models
import uuid
from .legal_entity import LegalEntity
from .external_entity import ExternalEntity


class Opportunity(models.Model):
    """
    Represents a funding or partnership opportunity.
    Tracks lifecycle but does NOT manage financial transactions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STAGE_CHOICES = (
        ("PROSPECT", "Prospect"),
        ("LOI", "LOI Submitted"),
        ("SUBMITTED", "Application Submitted"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("DECLINED", "Declined"),
        ("CLOSED", "Closed"),
    )

    OPPORTUNITY_TYPE = (
        ("GRANT", "Grant"),
        ("PARTNERSHIP", "Partnership"),
        ("SPONSORSHIP", "Sponsorship"),
        ("MISSION_SUPPORT", "Mission Support"),
    )

    # Legal routing (multi-entity support)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="opportunities"
    )

    external_entity = models.ForeignKey(
        ExternalEntity,
        on_delete=models.CASCADE,
        related_name="opportunities"
    )

    # Core information
    title = models.CharField(max_length=255)
    opportunity_type = models.CharField(max_length=30, choices=OPPORTUNITY_TYPE)

    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default="PROSPECT"
    )

    # Currency-aware (multi-country ready)
    currency = models.CharField(max_length=3)  # ISO currency code (CAD, USD, etc.)

    amount_requested = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    expected_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Lifecycle
    deadline = models.DateField(null=True, blank=True)
    submission_date = models.DateField(null=True, blank=True)
    decision_date = models.DateField(null=True, blank=True)

    # Internal scoring / probability (separate from StrategicScore)
    probability_score = models.IntegerField(default=0)  # 0–100%

    # Classification
    tags = models.ManyToManyField(
        "advancement.Tag",
        blank=True,
        related_name="opportunities"
    )

    # Internal notes
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-deadline", "-created_at"]
        indexes = [
            models.Index(fields=["stage"]),
            models.Index(fields=["legal_entity"]),
            models.Index(fields=["currency"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.external_entity.name}"

    @property
    def is_active(self):
        """Active means not declined or closed."""
        return self.stage not in ["DECLINED", "CLOSED"]