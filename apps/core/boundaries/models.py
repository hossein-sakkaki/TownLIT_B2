# apps/core/boundaries/models.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.boundaries.constants import (
    BOUNDARY_TYPE_CHOICES,
    BOUNDARY_SOURCE_CHOICES,
    BOUNDARY_STILLNESS,
    BOUNDARY_BOUNDARY,
    BOUNDARY_SOURCE_PROFILE,
)


class UserBoundary(models.Model):
    """
    Central Peace & Boundaries model.

    owner:
        The user who creates Stillness or Boundary.

    target:
        The user placed in Stillness or Boundary.

    boundary_type:
        - stillness: quiet distance, mostly affects owner's experience.
        - boundary: protective boundary, pauses direct interaction.

    Important:
        Boundary is one-directional in ownership, but interaction policy treats
        direct interaction as unavailable between both users when an active
        boundary exists in either direction.
    """

    id = models.BigAutoField(primary_key=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="boundaries_created",
        verbose_name=_("Owner"),
        db_index=True,
    )

    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="boundaries_received",
        verbose_name=_("Target"),
        db_index=True,
    )

    boundary_type = models.CharField(
        max_length=24,
        choices=BOUNDARY_TYPE_CHOICES,
        default=BOUNDARY_STILLNESS,
        db_index=True,
    )

    source = models.CharField(
        max_length=32,
        choices=BOUNDARY_SOURCE_CHOICES,
        default=BOUNDARY_SOURCE_PROFILE,
        db_index=True,
    )

    reason = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Short optional reason selected by the user.",
    )

    note = models.TextField(
        blank=True,
        default="",
        help_text="Private optional note visible only to the owner/admin tools.",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = _("User Boundary")
        verbose_name_plural = _("User Boundaries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "target", "boundary_type", "is_active"]),
            models.Index(fields=["target", "owner", "boundary_type", "is_active"]),
            models.Index(fields=["owner", "is_active", "boundary_type"]),
            models.Index(fields=["target", "is_active", "boundary_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "target", "boundary_type"],
                condition=Q(is_active=True),
                name="unique_active_boundary_per_type",
            ),
            models.CheckConstraint(
                check=~Q(owner=models.F("target")),
                name="prevent_self_boundary",
            ),
        ]

    def clean(self):
        super().clean()

        if self.owner_id and self.target_id and self.owner_id == self.target_id:
            raise ValidationError("You cannot create Stillness or Boundary with yourself.")

        if self.boundary_type not in {BOUNDARY_STILLNESS, BOUNDARY_BOUNDARY}:
            raise ValidationError("Invalid boundary type.")

    def __str__(self):
        return f"{self.owner_id} -> {self.target_id} ({self.boundary_type})"