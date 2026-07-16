# apps/accounts/models/username_reservation.py

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from validators.usernameValidators.constants import (
    USERNAME_REUSE_COOLDOWN_DAYS,
)
from validators.usernameValidators.username_normalizer import (
    normalize_username,
)


class UsernameReservation(models.Model):
    """
    Permanent historical username alias.

    A username that was previously owned by a user remains attached to that
    same user. This keeps old profile links valid and prevents identity
    confusion if an old username were reassigned to another account.

    expires_at is retained for backward compatibility and audit purposes, but
    alias resolution and reuse protection do not depend on its expiration.
    """

    username = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="username_reservations",
    )

    reserved_at = models.DateTimeField(
        default=timezone.now,
    )

    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Username Alias"
        verbose_name_plural = "Username Aliases"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["user", "username"]),
            models.Index(fields=["expires_at"]),
        ]

    def save(self, *args, **kwargs):
        self.username = normalize_username(
            self.username
        )

        if not self.expires_at:
            self.expires_at = (
                timezone.now()
                + timedelta(
                    days=USERNAME_REUSE_COOLDOWN_DAYS
                )
            )

        super().save(*args, **kwargs)

    @classmethod
    def reserve(
        cls,
        username: str,
        user,
    ):
        normalized = normalize_username(
            username
        )

        if not normalized or not user:
            return None

        expires_at = (
            timezone.now()
            + timedelta(
                days=USERNAME_REUSE_COOLDOWN_DAYS
            )
        )

        reservation, _ = cls.objects.update_or_create(
            username=normalized,
            defaults={
                "user": user,
                "reserved_at": timezone.now(),
                "expires_at": expires_at,
            },
        )

        return reservation

    @classmethod
    def is_reserved_for_other_user(
        cls,
        username: str,
        user,
    ) -> bool:
        """
        Old usernames are permanently protected from reassignment.

        The original owner may reclaim one of their own former usernames.
        """

        normalized = normalize_username(
            username
        )

        if not normalized:
            return False

        queryset = cls.objects.filter(
            username=normalized
        )

        if user is not None:
            queryset = queryset.exclude(
                user=user
            )

        return queryset.exists()

    @classmethod
    def user_for_alias(
        cls,
        username: str,
    ):
        normalized = normalize_username(
            username
        )

        if not normalized:
            return None

        reservation = (
            cls.objects
            .select_related("user")
            .filter(
                username=normalized,
            )
            .first()
        )

        if not reservation:
            return None

        return reservation.user

    def __str__(self):
        return self.username