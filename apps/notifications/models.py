# apps/notifications/models.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Index
from django.utils import timezone

from .constants import NOTIFICATION_TYPES, CHANNEL_DEFAULT


User = get_user_model()


# -----------------------------------------------------------------------------
# Campaign
# -----------------------------------------------------------------------------
class NotificationCampaign(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "General Announcement"
        APP_UPDATE = "app_update", "App Update"
        FEATURE = "feature", "New Feature"
        MAINTENANCE = "maintenance", "Maintenance"
        SECURITY = "security", "Security Notice"
        POLICY = "policy", "Policy Update"
        COMMUNITY = "community", "Community Announcement"
        EVENT = "event", "Event"

    class Audience(models.TextChoices):
        ALL = "all", "All Users"
        MEMBERS = "members", "Members"
        GUESTS = "guests", "Guests"
        STAFF = "staff", "Staff / Admins"
        SELECTED = "selected", "Selected Users"

    class Platform(models.TextChoices):
        ALL = "all", "All Platforms"
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"
        WEB = "web", "Web"
        MOBILE = "mobile", "iOS + Android"

    class ActionType(models.TextChoices):
        NONE = "none", "No Action"
        INTERNAL = "internal", "TownLIT Link"
        EXTERNAL = "external", "External Link"
        APP_STORE = "app_store", "Apple App Store"
        PLAY_STORE = "play_store", "Google Play"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    NOTIFICATION_TYPE_BY_CATEGORY = {
        Category.GENERAL: "townlit_announcement",
        Category.APP_UPDATE: "townlit_app_update",
        Category.FEATURE: "townlit_feature_update",
        Category.MAINTENANCE: "townlit_maintenance",
        Category.SECURITY: "townlit_security_notice",
        Category.POLICY: "townlit_policy_update",
        Category.COMMUNITY: "townlit_community",
        Category.EVENT: "townlit_event",
    }

    EMAIL_ALLOWED_CATEGORIES = {
        Category.MAINTENANCE,
        Category.SECURITY,
        Category.POLICY,
    }

    id = models.BigAutoField(primary_key=True)

    internal_name = models.CharField(
        max_length=160,
        help_text="Internal name shown only to TownLIT admins.",
    )

    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.GENERAL,
    )

    title = models.CharField(
        max_length=140,
        help_text="Short notification title.",
    )

    message = models.TextField(
        help_text="User-facing notification message.",
    )

    audience_type = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
    )

    platform_scope = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.ALL,
    )

    selected_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="selected_notification_campaigns",
        blank=True,
        help_text="Used only when audience is Selected Users.",
    )

    send_push = models.BooleanField(
        default=True,
        help_text="Send Push in addition to the in-app notification.",
    )

    send_email = models.BooleanField(
        default=False,
        help_text="Reserved for important service, security, and policy notices.",
    )

    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        default=ActionType.NONE,
    )

    action_label = models.CharField(
        max_length=40,
        blank=True,
        help_text="Example: Update Now, Learn More, Open TownLIT.",
    )

    action_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="TownLIT path, universal link, App Store URL, or external URL.",
    )

    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Leave empty to publish as soon as the campaign is queued.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    total_recipients = models.PositiveIntegerField(default=0)
    processed_count = models.PositiveIntegerField(default=0)
    in_app_count = models.PositiveIntegerField(default=0)
    push_sent_count = models.PositiveIntegerField(default=0)
    email_queued_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)

    last_error = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_notification_campaigns",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="notif_camp_sched_idx"),
            models.Index(fields=["category", "platform_scope"], name="notif_camp_target_idx"),
        ]

    @property
    def notification_type(self) -> str:
        return self.NOTIFICATION_TYPE_BY_CATEGORY.get(
            self.category,
            "townlit_announcement",
        )

    def clean(self):
        super().clean()

        if self.send_email and self.category not in self.EMAIL_ALLOWED_CATEGORIES:
            raise ValidationError({
                "send_email": (
                    "Email is reserved for Maintenance, Security, and Policy campaigns. "
                    "Use Push + In-App for routine product announcements."
                )
            })

        if self.action_type == self.ActionType.NONE:
            if self.action_url or self.action_label:
                raise ValidationError({
                    "action_type": "Choose an action type when an action URL or label is provided."
                })
            return

        if not self.action_url.strip():
            raise ValidationError({"action_url": "An action URL is required."})

        if not self.action_label.strip():
            raise ValidationError({"action_label": "An action label is required."})

        if (
            self.action_type == self.ActionType.APP_STORE
            and self.platform_scope != self.Platform.IOS
        ):
            raise ValidationError({
                "platform_scope": "Apple App Store campaigns must target iOS."
            })

        if (
            self.action_type == self.ActionType.PLAY_STORE
            and self.platform_scope != self.Platform.ANDROID
        ):
            raise ValidationError({
                "platform_scope": "Google Play campaigns must target Android."
            })

    def __str__(self):
        return f"{self.internal_name} ({self.get_status_display()})"


# -----------------------------------------------------------------------------
# User preferences
# -----------------------------------------------------------------------------
class UserNotificationPreference(models.Model):
    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        related_name="notification_preferences",
        on_delete=models.CASCADE,
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
    )

    enabled = models.BooleanField(default=True)

    # 1: Push, 2: WebSocket, 4: Email
    channels_mask = models.PositiveIntegerField(default=CHANNEL_DEFAULT)

    class Meta:
        unique_together = ("user", "notification_type")

    def __str__(self):
        state = "Enabled" if self.enabled else "Disabled"
        return f"{self.user.username} - {self.notification_type} - {state}"


# -----------------------------------------------------------------------------
# Notification
# -----------------------------------------------------------------------------
class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        related_name="notifications",
        on_delete=models.CASCADE,
    )

    actor = models.ForeignKey(
        User,
        related_name="actor_notifications",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    campaign = models.ForeignKey(
        NotificationCampaign,
        related_name="notifications",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=140,
        blank=True,
        default="",
    )

    message = models.TextField()

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
    )

    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target_object = GenericForeignKey("target_content_type", "target_object_id")

    action_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    action_object_id = models.PositiveIntegerField(null=True, blank=True)
    action_object = GenericForeignKey("action_content_type", "action_object_id")

    link = models.URLField(null=True, blank=True)

    action_label = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    dedupe_key = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        validators=[MinLengthValidator(8)],
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"],
                name="notif_unique_campaign_user",
            ),
        ]

        indexes = [
            Index(fields=["user", "-created_at"]),
            Index(fields=["is_read", "user"]),
            Index(fields=["notification_type"]),
            Index(fields=["dedupe_key"]),
        ]

    def __str__(self):
        return f"Notif<{self.id}> to {self.user_id}: {self.message[:50]}"

    def get_target_safe(self):
        """Return the target or None."""
        if not self.target_content_type or not self.target_object_id:
            return None

        try:
            return self.target_object
        except ObjectDoesNotExist:
            return None

    def is_target_unavailable(self) -> bool:
        """Check whether the target is unavailable."""
        obj = self.get_target_safe()

        if obj is None:
            return True

        return (
            getattr(obj, "is_active", True) is False
            or getattr(obj, "is_hidden", False) is True
            or getattr(obj, "is_suspended", False) is True
            or getattr(obj, "is_restricted", False) is True
        )


# -----------------------------------------------------------------------------
# Campaign delivery
# -----------------------------------------------------------------------------
class NotificationCampaignDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.BigAutoField(primary_key=True)

    campaign = models.ForeignKey(
        NotificationCampaign,
        related_name="deliveries",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notification_campaign_deliveries",
        on_delete=models.CASCADE,
    )

    notification = models.OneToOneField(
        Notification,
        related_name="campaign_delivery",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    push_sent = models.BooleanField(default=False)
    email_queued = models.BooleanField(default=False)

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("campaign_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"],
                name="notif_unique_campaign_delivery",
            ),
        ]
        indexes = [
            models.Index(
                fields=["campaign", "status"],
                name="notif_deliv_camp_stat_idx",
            ),
        ]

    def __str__(self):
        return f"Campaign<{self.campaign_id}> -> User<{self.user_id}>"


# -----------------------------------------------------------------------------
# Notification log
# -----------------------------------------------------------------------------
class NotificationLog(models.Model):
    id = models.BigAutoField(primary_key=True)

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log n#{self.notification_id} -> u#{self.recipient_id}"