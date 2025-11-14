# apps/notifications/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import Index
from django.core.validators import MinLengthValidator
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.functions import Now
from django.contrib.auth import get_user_model

from .constants import NOTIFICATION_TYPES

User = get_user_model()

# -----------------------------------------------------------------------------
class UserNotificationPreference(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, related_name='notification_preferences', on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    enabled = models.BooleanField(default=True)
    # Optional channel mask (default = both push+ws)
    channels_mask = models.PositiveIntegerField(default=3)  # 1:push, 2:ws

    class Meta:
        unique_together = ('user', 'notification_type')

    def __str__(self):
        return f"{self.user.username} - {self.notification_type} - {'Enabled' if self.enabled else 'Disabled'}"


# -----------------------------------------------------------------------------
class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)

    # Recipient
    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)

    # Actor (who did the action)
    actor = models.ForeignKey(User, related_name='actor_notifications', on_delete=models.SET_NULL, null=True, blank=True)

    # Core fields
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Target = the thing being notified about (e.g., a Post or Comment)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target_object = GenericForeignKey('target_content_type', 'target_object_id')

    # Action object = the event record (e.g., Reaction row, Comment row)
    action_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    action_object_id = models.PositiveIntegerField(null=True, blank=True)
    action_object = GenericForeignKey('action_content_type', 'action_object_id')

    # Optional deep-link
    link = models.URLField(null=True, blank=True)

    # For idempotency/dedupe (same actor + action + target within a window)
    dedupe_key = models.CharField(max_length=120, null=True, blank=True, validators=[MinLengthValidator(8)])

    class Meta:
        ordering = ['-created_at']
        indexes = [
            Index(fields=['user', '-created_at']),
            Index(fields=['is_read', 'user']),
            Index(fields=['notification_type']),
            Index(fields=['dedupe_key']),
        ]

    def __str__(self):
        return f"Notif<{self.id}> to {self.user_id}: {self.message[:50]}"

    # -------- Helper methods for safety / cleanup --------

    def get_target_safe(self):
        """
        Safely return target object (or None if deleted / missing).
        """
        if not self.target_content_type or not self.target_object_id:
            return None
        try:
            return self.target_object
        except ObjectDoesNotExist:
            return None

    def is_target_unavailable(self) -> bool:
        """
        Determine if the target is effectively unavailable to users.
        - Missing object
        - OR flagged as inactive/hidden/suspended/restricted
        """
        obj = self.get_target_safe()
        if obj is None:
            return True  # missing target → treat as unavailable

        is_active = getattr(obj, "is_active", True)
        is_hidden = getattr(obj, "is_hidden", False)
        is_suspended = getattr(obj, "is_suspended", False)
        is_restricted = getattr(obj, "is_restricted", False)

        return (
            is_active is False
            or is_hidden is True
            or is_suspended is True
            or is_restricted is True
        )

# -----------------------------------------------------------------------------
class NotificationLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log n#{self.notification_id} -> u#{self.recipient_id}"
