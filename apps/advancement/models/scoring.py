# apps/advancement/models/scoring.py

from django.db import models
import uuid
from .external_entity import ExternalEntity


class StrategicScore(models.Model):
    """
    Strategic evaluation of an ExternalEntity.
    Separate from Opportunity scoring for clean architecture.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    external_entity = models.OneToOneField(
        ExternalEntity,
        on_delete=models.CASCADE,
        related_name="strategic_score"
    )

    # Core scoring dimensions (0-10 scale)
    mission_alignment = models.IntegerField(default=0)
    funding_capacity = models.IntegerField(default=0)
    access_level = models.IntegerField(default=0)
    influence_value = models.IntegerField(default=0)
    effort_required = models.IntegerField(default=0)

    # Internal commentary
    notes = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Strategic Score"
        verbose_name_plural = "Strategic Scores"

    def __str__(self):
        return f"{self.external_entity.name} Strategic Score"

    @property
    def total_score(self):
        """
        Weighted strategic score calculation.
        Effort reduces final score.
        """
        positive = (
            self.mission_alignment +
            self.funding_capacity +
            self.access_level +
            self.influence_value
        )
        adjusted = positive - self.effort_required
        return max(adjusted, 0)