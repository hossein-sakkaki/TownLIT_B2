# apps/core/visibility/mixins.py
from django.db import models
from .constants import VISIBILITY_CHOICES, VISIBILITY_GLOBAL


class VisibilityModelMixin(models.Model):
    """
    Adds visibility data to content models.
    Contains NO logic — only data.
    """

    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_GLOBAL,
        db_index=True,
        verbose_name="Visibility",
    )

    is_hidden = models.BooleanField(
        default=False,
        help_text="UI-level hide (not moderation).",
    )
    
    class Meta:
        abstract = True
