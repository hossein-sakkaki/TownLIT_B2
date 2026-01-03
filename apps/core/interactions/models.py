# apps/core/interactions/models.py

from django.db import models
 

class ReactionBreakdownMixin(models.Model):
    """
    Stores per-reaction-type counts.
    Example:
    {
        "like": 10,
        "amen": 3,
        "faithfire": 1
    }
    """

    reactions_breakdown = models.JSONField(default=dict)

    class Meta:
        abstract = True
