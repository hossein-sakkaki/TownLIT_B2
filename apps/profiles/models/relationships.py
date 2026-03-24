# apps/profiles/models/relationships.py

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

from apps.profiles.constants.friendship import (
    FRIENDSHIP_STATUS_CHOICES,
)
from apps.profiles.constants.fellowship import (
    FELLOWSHIP_RELATIONSHIP_CHOICES,
    RECIPROCAL_FELLOWSHIP_CHOICES,
    FELLOWSHIP_STATUS_CHOICES,
)
CustomUser = get_user_model()


class Friendship(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        db_index=True,
        related_name="friendships_initiated",
        verbose_name="Initiator",
    )
    to_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        db_index=True,
        related_name="friendships_received",
        verbose_name="Friend",
    )
    status = models.CharField(
        max_length=20,
        choices=FRIENDSHIP_STATUS_CHOICES,
        default="pending",
        verbose_name="Status",
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created At")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Deleted At")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                condition=models.Q(is_active=True),
                name="unique_active_friendship",
            )
        ]
        verbose_name = "Friendship"
        verbose_name_plural = "Friendships"

    def __str__(self):
        return f"{self.from_user.username} to {self.to_user.username} ({self.status})"

    def get_absolute_url(self):
        # Return frontend route for friendship notifications.
        try:
            if self.status == "pending":
                return "/settings/friendships?tab=requests"

            actor = getattr(self, "from_user", None)
            target = getattr(self, "to_user", None)

            if self.status in ["deleted", "cancelled"] and actor:
                return f"/lit/{actor.username}"

            if target:
                return f"/lit/{target.username}"

            return "/lit/"
        except Exception:
            return "/lit/"


class Fellowship(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="fellowship_sent",
        verbose_name=_("From User"),
    )
    to_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="fellowship_received",
        verbose_name=_("To User"),
    )
    fellowship_type = models.CharField(
        max_length=20,
        choices=FELLOWSHIP_RELATIONSHIP_CHOICES,
        verbose_name=_("Fellowship Type"),
    )
    reciprocal_fellowship_type = models.CharField(
        max_length=50,
        choices=RECIPROCAL_FELLOWSHIP_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Reciprocal Fellowship Type"),
    )
    status = models.CharField(
        max_length=20,
        choices=FELLOWSHIP_STATUS_CHOICES,
        default="Pending",
        verbose_name=_("Status"),
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Fellowship")
        verbose_name_plural = _("Fellowships")
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "from_user",
                    "to_user",
                    "fellowship_type",
                    "reciprocal_fellowship_type",
                ],
                name="unique_fellowship_per_type",
            )
        ]

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({self.fellowship_type})"

    def get_absolute_url(self):
        # Return frontend route for fellowship notifications.
        try:
            if self.status == "Pending":
                return "/settings/lit-covenant"

            if self.status == "Cancelled" and self.from_user:
                return f"/lit/{self.from_user.username}"

            if self.to_user:
                return f"/lit/{self.to_user.username}"

            return "/lit/"
        except Exception:
            return "/lit/"