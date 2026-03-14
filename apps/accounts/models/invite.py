# apps/accounts/models/invite.py

from django.conf import settings
from django.db import models
from django.utils import timezone


class InviteCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    email = models.EmailField(null=True, blank=True, help_text="Optional: restrict to specific email")
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    is_used = models.BooleanField(default=False)

    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='used_invite_code',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    invite_email_sent = models.BooleanField(default=False)
    invite_email_sent_at = models.DateTimeField(null=True, blank=True)

    def mark_as_used(self, user):
        self.is_used = True
        self.used_by = user
        self.used_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.code} ({'USED' if self.is_used else 'UNUSED'})"