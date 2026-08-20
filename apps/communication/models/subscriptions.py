# apps/communication/models/subscriptions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.communication.constants import (
    EmailSubscriptionSource,
    EmailSubscriptionStatus,
    EmailUnsubscribeScope,
)

from .base import PublicCommunicationRecord


class EmailTopic(PublicCommunicationRecord):
    """
    User-manageable email subscription topic.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Topic Name",
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        verbose_name="Slug",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
    )
    allow_unsubscribe = models.BooleanField(
        default=True,
        verbose_name="User Can Unsubscribe",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name="Sort Order",
    )

    class Meta:
        verbose_name = "Email Topic"
        verbose_name_plural = "Email Topics"
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()

        super().save(*args, **kwargs)

    def _build_unique_slug(self):
        base_slug = slugify(self.name) or "email-topic"
        candidate = base_slug
        suffix = 2

        queryset = type(self).objects.exclude(pk=self.pk)

        while queryset.filter(slug=candidate).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        return candidate

    def __str__(self):
        return self.name


class EmailSubscriptionPreference(PublicCommunicationRecord):
    """
    Per-topic subscription preference.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_subscription_preferences",
        verbose_name="User",
    )
    email = models.EmailField(
        db_index=True,
        verbose_name="Email Address",
    )
    topic = models.ForeignKey(
        EmailTopic,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name="Email Topic",
    )
    status = models.CharField(
        max_length=20,
        choices=EmailSubscriptionStatus.choices,
        default=EmailSubscriptionStatus.SUBSCRIBED,
        db_index=True,
        verbose_name="Status",
    )
    source = models.CharField(
        max_length=20,
        choices=EmailSubscriptionSource.choices,
        default=EmailSubscriptionSource.ACCOUNT,
        verbose_name="Preference Source",
    )

    subscribed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Subscribed At",
    )
    unsubscribed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Unsubscribed At",
    )

    class Meta:
        verbose_name = "Email Subscription Preference"
        verbose_name_plural = "Email Subscription Preferences"
        ordering = ["email", "topic_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["email", "topic"],
                name="comm_email_topic_pref_unique",
            ),
        ]

    def clean(self):
        super().clean()

        email = self.email

        if not email and self.user_id:
            email = self.user.email

        if not email:
            raise ValidationError({
                "email": "An email address is required.",
            })

    def save(self, *args, **kwargs):
        if not self.email and self.user_id:
            self.email = self.user.email

        self.email = (self.email or "").strip().lower()

        if self.status == EmailSubscriptionStatus.SUBSCRIBED:
            self.subscribed_at = self.subscribed_at or timezone.now()
            self.unsubscribed_at = None
        else:
            self.unsubscribed_at = self.unsubscribed_at or timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} · {self.topic.name}"


class UnsubscribedUser(models.Model):
    """
    Global optional-email suppression record.

    Kept compatible with the existing unsubscribe flow.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="communication_unsubscribe",
        verbose_name="Registered User",
    )
    email = models.EmailField(
        unique=True,
        blank=True,
        default="",
        verbose_name="Email Address",
    )
    scope = models.CharField(
        max_length=20,
        choices=EmailUnsubscribeScope.choices,
        default=EmailUnsubscribeScope.MARKETING,
        verbose_name="Unsubscribe Scope",
    )
    reason = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Reason",
    )
    source = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Source",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata",
    )
    unsubscribed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="Unsubscribed At",
    )

    class Meta:
        verbose_name = "Unsubscribed Contact"
        verbose_name_plural = "Unsubscribed Contacts"
        ordering = ["-unsubscribed_at"]

    def clean(self):
        super().clean()

        email = self.email

        if not email and self.user_id:
            email = self.user.email

        if not email:
            raise ValidationError({
                "email": "An email address is required.",
            })

    def save(self, *args, **kwargs):
        if not self.email and self.user_id:
            self.email = self.user.email

        self.email = (self.email or "").strip().lower()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.email or str(self.user)