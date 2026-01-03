# apps/core/interactions/mixins.py

from django.db import models


class InteractionCounterMixin(models.Model):
    """
    Denormalized counters for feed performance.
    Generic for any content type (Moment, Testimony, etc).
    """

    # -----------------------------
    # Comments
    # -----------------------------
    comments_count = models.PositiveIntegerField(default=0)
    recomments_count = models.PositiveIntegerField(default=0)

    # -----------------------------
    # Reactions (total)
    # -----------------------------
    reactions_count = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
