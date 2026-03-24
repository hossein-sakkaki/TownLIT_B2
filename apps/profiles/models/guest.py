# apps/profiles/models/guest.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

from utils.common.utils import SlugMixin

CustomUser = get_user_model()


class GuestUser(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="guest_profile",
        verbose_name="User",
    )
    biography = models.CharField(
        max_length=2000,
        null=True,
        blank=True,
        verbose_name="Biography",
    )
    is_privacy = models.BooleanField(
        default=False,
        verbose_name="Is Privacy",
    )
    register_date = models.DateField(default=timezone.localdate, verbose_name='Register Date')
    is_migrated = models.BooleanField(
        default=False,
        verbose_name="Is Migrated",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Is Active",
    )

    url_name = "guest_user_detail"

    class Meta:
        verbose_name = "2. Guest User"
        verbose_name_plural = "2. Guest Users"

    def __str__(self):
        return self.user.username

    def get_slug_source(self):
        return self.user.username