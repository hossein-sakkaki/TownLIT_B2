# apps/profiles/models/transitions.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.profiles.constants.migration import MIGRATION_CHOICES

CustomUser = get_user_model()


class MigrationHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="migration_history",
    )
    migration_type = models.CharField(
        max_length=20,
        choices=MIGRATION_CHOICES,
    )
    migration_date = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Migration History"
        verbose_name_plural = "Migration Histories"

    def __str__(self):
        return f"{self.user.username} - {self.migration_type} on {self.migration_date}"