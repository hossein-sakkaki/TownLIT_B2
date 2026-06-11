# apps/accounts/models/username_reservation.py

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from validators.usernameValidators.constants import USERNAME_REUSE_COOLDOWN_DAYS
from validators.usernameValidators.username_normalizer import normalize_username


class UsernameReservation(models.Model):
    """
    Temporarily reserves old usernames after change.
    """
    username = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="username_reservations",
    )
    reserved_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Username Reservation"
        verbose_name_plural = "Username Reservations"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["expires_at"]),
        ]

    def save(self, *args, **kwargs):
        self.username = normalize_username(self.username)

        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=USERNAME_REUSE_COOLDOWN_DAYS)

        super().save(*args, **kwargs)

    @classmethod
    def reserve(cls, username: str, user):
        username = normalize_username(username)

        if not username:
            return None

        expires_at = timezone.now() + timedelta(days=USERNAME_REUSE_COOLDOWN_DAYS)

        reservation, _ = cls.objects.update_or_create(
            username=username,
            defaults={
                "user": user,
                "reserved_at": timezone.now(),
                "expires_at": expires_at,
            },
        )

        return reservation

    @classmethod
    def is_reserved_for_other_user(cls, username: str, user) -> bool:
        username = normalize_username(username)

        return cls.objects.filter(
            username=username,
            expires_at__gt=timezone.now(),
        ).exclude(user=user).exists()

    def __str__(self):
        return self.username