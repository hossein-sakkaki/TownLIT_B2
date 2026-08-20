# apps/communication/models/campaigns.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models

from apps.communication.constants import (
    ALL_ACTIVE,
    TARGET_GROUP_CHOICES,
    CampaignStatus,
    CampaignType,
    LAYOUT_BASE_SITE,
)

from .base import CommunicationRecord, EmailContentBlockBase


class EmailCampaign(CommunicationRecord):
    """
    Professional admin-managed email campaign.
    """

    title = models.CharField(
        max_length=255,
        verbose_name="Campaign Title",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Internal Description",
    )
    campaign_type = models.CharField(
        max_length=30,
        choices=CampaignType.choices,
        default=CampaignType.ANNOUNCEMENT,
        db_index=True,
        verbose_name="Campaign Type",
    )

    subject = models.CharField(
        max_length=255,
        verbose_name="Email Subject",
    )
    preheader_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Preheader Text",
    )

    template = models.ForeignKey(
        "communication.EmailTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
        verbose_name="Email Template",
    )
    theme = models.ForeignKey(
        "communication.EmailTheme",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
        verbose_name="Email Theme Override",
    )

    custom_html = RichTextUploadingField(
        blank=True,
        verbose_name="Custom Email Body",
    )
    content_version = models.PositiveIntegerField(
        default=1,
        verbose_name="Content Version",
    )

    audience = models.ForeignKey(
        "communication.EmailAudience",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
        verbose_name="Saved Audience",
    )
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="manual_campaigns",
        verbose_name="Specific Recipients",
    )

    # Legacy preset support.
    target_group = models.CharField(
        max_length=50,
        choices=TARGET_GROUP_CHOICES,
        default=ALL_ACTIVE,
        db_index=True,
        verbose_name="Quick Audience Preset",
    )

    topic = models.ForeignKey(
        "communication.EmailTopic",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
        verbose_name="Subscription Topic",
    )

    ignore_unsubscribe = models.BooleanField(
        default=False,
        verbose_name="Bypass Unsubscribe Protection",
        help_text=(
            "Use only for required legal, security, safety, "
            "or operational communication."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
        db_index=True,
        verbose_name="Campaign Status",
    )

    scheduled_time = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Scheduled Send Time",
    )
    schedule_timezone = models.CharField(
        max_length=64,
        default="UTC",
        verbose_name="Scheduling Time Zone",
    )

    queued_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Queued At",
    )
    last_dispatch_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Dispatch Attempt",
    )
    dispatch_attempt_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Dispatch Attempts",
    )
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name="Celery Task ID",
    )

    last_test_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Test Sent At",
    )

    last_test_email = models.EmailField(
        blank=True,
        default="",
        verbose_name="Last Test Email",
    )

    last_test_content_version = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Last Tested Content Version",
    )

    test_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name="Test Email",
    )
    tag = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Campaign Tag",
    )

    from_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Sender Name Override",
    )
    reply_to_email = models.EmailField(
        blank=True,
        verbose_name="Reply-To Email",
    )

    track_opens = models.BooleanField(
        default=True,
        verbose_name="Track Opens",
    )
    track_clicks = models.BooleanField(
        default=True,
        verbose_name="Track Clicks",
    )

    utm_source = models.CharField(
        max_length=100,
        blank=True,
        default="townlit_email",
        verbose_name="UTM Source",
    )
    utm_medium = models.CharField(
        max_length=100,
        blank=True,
        default="email",
        verbose_name="UTM Medium",
    )
    utm_campaign = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="UTM Campaign",
    )

    review_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Review Requested At",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_campaigns_approved",
        verbose_name="Approved By",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Approved At",
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Sending Started At",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Sent At",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completed At",
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Canceled At",
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Failed At",
    )

    recipient_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Recipients",
    )
    sent_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Sent",
    )
    delivered_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Delivered",
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Failed",
    )
    bounced_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Bounced",
    )
    complaint_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Complaints",
    )
    open_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Total Opens",
    )
    unique_open_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Unique Opens",
    )
    click_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Total Clicks",
    )
    unique_click_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Unique Clicks",
    )
    unsubscribe_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Unsubscribes",
    )

    last_error = models.TextField(
        blank=True,
        verbose_name="Last Error",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_campaigns_created",
        verbose_name="Created By",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_campaigns_updated",
        verbose_name="Updated By",
    )

    class Meta:
        verbose_name = "Email Campaign"
        verbose_name_plural = "Email Campaigns"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "scheduled_time"],
                name="comm_cmp_status_sched_idx",
            ),
            models.Index(
                fields=["campaign_type", "status"],
                name="comm_cmp_type_status_idx",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def effective_theme(self):
        if self.theme_id:
            return self.theme

        if self.template_id and self.template.theme_id:
            return self.template.theme

        return None

    @property
    def effective_layout(self):
        theme = self.effective_theme

        if theme:
            return theme.layout

        if self.template_id:
            return self.template.layout

        return LAYOUT_BASE_SITE

    @property
    def uses_block_builder(self):
        if not self.pk:
            return False

        return self.content_blocks.filter(is_enabled=True).exists()

    @property
    def can_edit_content(self):
        return self.status in {
            CampaignStatus.DRAFT,
            CampaignStatus.REVIEW,
            CampaignStatus.READY,
            CampaignStatus.PAUSED,
            CampaignStatus.FAILED,
        }

    @property
    def is_terminal(self):
        return self.status in {
            CampaignStatus.SENT,
            CampaignStatus.CANCELED,
        }

    @property
    def open_rate(self):
        if not self.sent_count:
            return 0.0

        return round(
            self.unique_open_count / self.sent_count * 100,
            2,
        )

    @property
    def click_rate(self):
        if not self.sent_count:
            return 0.0

        return round(
            self.unique_click_count / self.sent_count * 100,
            2,
        )
        
    @property
    def has_current_test(self):
        if not self.last_test_sent_at:
            return False

        if not self.last_test_content_version:
            return False

        if (
            self.last_test_content_version
            != self.content_version
        ):
            return False

        if not self.test_email:
            return False

        return (
            (self.last_test_email or "").strip().lower()
            == self.test_email.strip().lower()
        )


class EmailCampaignBlock(EmailContentBlockBase):
    """
    Editable visual content block owned by one campaign.
    """

    campaign = models.ForeignKey(
        EmailCampaign,
        on_delete=models.CASCADE,
        related_name="content_blocks",
        verbose_name="Email Campaign",
    )

    class Meta:
        verbose_name = "Email Campaign Block"
        verbose_name_plural = "Email Campaign Blocks"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(
                fields=["campaign", "sort_order"],
                name="comm_cmp_block_order_idx",
            ),
        ]

    def __str__(self):
        return self.name or (
            f"{self.get_block_type_display()} #{self.sort_order}"
        )