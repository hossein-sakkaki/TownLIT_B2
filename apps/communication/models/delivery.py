# apps/communication/models/delivery.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.communication.constants import (
    EmailDeliveryProvider,
    EmailDeliveryStatus,
    EmailEventType,
)


class EmailLog(models.Model):
    """
    One campaign delivery attempt for one recipient.
    """

    campaign = models.ForeignKey(
        "communication.EmailCampaign",
        on_delete=models.CASCADE,
        related_name="email_logs",
        verbose_name="Email Campaign",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_email_logs",
        verbose_name="Registered User",
    )
    external_contact = models.ForeignKey(
        "communication.ExternalContact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
        verbose_name="External Contact",
    )
    email = models.EmailField(
        db_index=True,
        verbose_name="Recipient Email",
    )

    status = models.CharField(
        max_length=20,
        choices=EmailDeliveryStatus.choices,
        default=EmailDeliveryStatus.SENT,
        db_index=True,
        verbose_name="Delivery Status",
    )
    provider = models.CharField(
        max_length=20,
        choices=EmailDeliveryProvider.choices,
        default=EmailDeliveryProvider.AWS_SES,
        verbose_name="Delivery Provider",
    )
    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name="Provider Message ID",
    )

    queued_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Queued At",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Sent At",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Delivered At",
    )

    opened = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Email Opened",
    )
    opened_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="First Opened At",
    )
    open_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Open Count",
    )

    clicked = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Link Clicked",
    )
    clicked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="First Clicked At",
    )
    click_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Click Count",
    )

    bounced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Bounced At",
    )
    complained_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Complaint At",
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Failed At",
    )

    failure_code = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Failure Code",
    )
    failure_message = models.TextField(
        blank=True,
        verbose_name="Failure Message",
    )
    last_event_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Event At",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Delivery Metadata",
    )

    class Meta:
        verbose_name = "Email Delivery"
        verbose_name_plural = "Email Deliveries"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(
                fields=["campaign", "status"],
                name="comm_log_cmp_status_idx",
            ),
            models.Index(
                fields=["email", "sent_at"],
                name="comm_log_email_sent_idx",
            ),
        ]

    def __str__(self):
        return f"{self.email} – {self.campaign.title}"


class EmailEvent(models.Model):
    """
    Immutable delivery event received or recorded for an email.
    """

    delivery = models.ForeignKey(
        EmailLog,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Email Delivery",
    )
    event_type = models.CharField(
        max_length=20,
        choices=EmailEventType.choices,
        db_index=True,
        verbose_name="Event Type",
    )
    occurred_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="Occurred At",
    )

    url = models.URLField(
        max_length=2000,
        blank=True,
        verbose_name="Clicked URL",
    )
    provider_event_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Provider Event ID",
    )
    dedupe_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        verbose_name="Deduplication Key",
    )

    user_agent = models.TextField(
        blank=True,
        verbose_name="User Agent",
    )
    ip_hash = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="IP Hash",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Event Metadata",
    )

    class Meta:
        verbose_name = "Email Event"
        verbose_name_plural = "Email Events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["delivery", "event_type"],
                name="comm_evt_log_type_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.delivery.email} · "
            f"{self.get_event_type_display()}"
        )


class EmailCampaignDailyMetric(models.Model):
    """
    Daily aggregated campaign analytics.
    """

    campaign = models.ForeignKey(
        "communication.EmailCampaign",
        on_delete=models.CASCADE,
        related_name="daily_metrics",
        verbose_name="Email Campaign",
    )
    date = models.DateField(
        db_index=True,
        verbose_name="Date",
    )

    sent = models.PositiveIntegerField(default=0)
    delivered = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    bounced = models.PositiveIntegerField(default=0)
    complaints = models.PositiveIntegerField(default=0)

    opens = models.PositiveIntegerField(default=0)
    unique_opens = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    unsubscribes = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Email Campaign Daily Metric"
        verbose_name_plural = "Email Campaign Daily Metrics"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "date"],
                name="comm_cmp_daily_metric_unique",
            ),
        ]

    def __str__(self):
        return f"{self.campaign.title} · {self.date}"