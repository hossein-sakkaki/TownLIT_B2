# apps/accounts/models/session_security.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Persisted per-account security generation; isolated from user profile data.

A missing row represents generation zero for compatibility with existing
accounts and JWTs. Rows are created only when revocation is requested.
"""

from django.conf import settings
from django.db import models


class UserAuthSessionState(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="auth_session_state",
    )
    generation = models.PositiveBigIntegerField(default=0)
    last_revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Auth Session State"
        verbose_name_plural = "User Auth Session States"

    def __str__(self):
        return f"user_id={self.user_id} generation={self.generation}"
