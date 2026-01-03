# apps/core/moderation/mixins.py

from django.db import models
from django.utils import timezone


class ModerationTargetMixin(models.Model):
    """
    Contract for any model that can be:
    - reported
    - reviewed by Sanctuary
    - suspended / deactivated by moderation outcome

    IMPORTANT:
    - reports_count is HISTORICAL / cumulative
    - active report waves are tracked elsewhere (SanctuaryRequest)
    """

    # -------------------------------------------------
    # Historical moderation counter (cumulative)
    # -------------------------------------------------
    reports_count = models.PositiveIntegerField(
        default=0,
        help_text="Historical cumulative reports count (not active wave)."
    )

    # -------------------------------------------------
    # Moderation enforcement flags
    # -------------------------------------------------
    is_suspended = models.BooleanField(
        default=False,
        help_text="System-level suspension due to moderation outcome."
    )

    is_active = models.BooleanField(
        default=True,
        help_text="System-level activation flag (false = removed from feeds)."
    )

    # -------------------------------------------------
    # Optional audit helpers (future-proof, no logic)
    # -------------------------------------------------
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when target was suspended."
    )

    suspension_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional reason code or short description."
    )

    class Meta:
        abstract = True

    # -------------------------------------------------
    # Tiny helpers (OPTIONAL – safe to ignore)
    # -------------------------------------------------
    def suspend(self, *, reason: str | None = None, commit: bool = True):
        """
        Convenience helper.
        Sanctuary may or may not use this directly.
        """
        self.is_suspended = True
        self.is_active = False
        self.suspended_at = timezone.now()
        if reason:
            self.suspension_reason = reason

        if commit:
            self.save(update_fields=[
                "is_suspended",
                "is_active",
                "suspended_at",
                "suspension_reason",
            ])

    def unsuspend(self, *, commit: bool = True):
        """
        Reverse suspension (used on rejected outcomes).
        """
        self.is_suspended = False
        self.suspended_at = None
        self.suspension_reason = None

        if commit:
            self.save(update_fields=[
                "is_suspended",
                "suspended_at",
                "suspension_reason",
            ])
