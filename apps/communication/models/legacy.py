# apps/communication/models/legacy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models
from django.utils import timezone


class DraftCampaign(models.Model):
    """
    Legacy draft metadata kept until data migration is complete.
    """

    campaign = models.OneToOneField(
        "communication.EmailCampaign",
        on_delete=models.CASCADE,
        related_name="draft",
        verbose_name="Related Campaign",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Draft Notes",
    )
    last_edited = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Edited At",
    )

    class Meta:
        verbose_name = "Legacy Draft Campaign"
        verbose_name_plural = "Legacy Draft Campaigns"
        ordering = ["-last_edited"]

    def __str__(self):
        return f"Draft: {self.campaign.title}"


class ScheduledEmail(models.Model):
    """
    Legacy scheduler kept until campaign scheduling migration is complete.
    """

    campaign = models.ForeignKey(
        "communication.EmailCampaign",
        on_delete=models.CASCADE,
        related_name="legacy_schedules",
        verbose_name="Email Campaign",
    )
    run_at = models.DateTimeField(
        verbose_name="Scheduled Run Time",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_scheduled_emails",
        verbose_name="Scheduled By",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created At",
    )
    executed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Executed At",
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name="Sent",
    )

    class Meta:
        verbose_name = "Legacy Scheduled Email"
        verbose_name_plural = "Legacy Scheduled Emails"
        ordering = ["-run_at"]

    def __str__(self):
        return f"Scheduled: {self.campaign.title} @ {self.run_at}"


class ExternalEmailCampaign(models.Model):
    """
    Legacy file-driven external campaign.
    """

    title = models.CharField(
        max_length=255,
        verbose_name="Campaign Title",
    )
    subject = models.CharField(
        max_length=255,
        verbose_name="Email Subject",
    )
    template = models.ForeignKey(
        "communication.EmailTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_external_campaigns",
        verbose_name="Email Template",
    )
    html_body = RichTextUploadingField(
        verbose_name="Custom Email Body",
    )
    csv_file = models.FileField(
        upload_to="external_campaigns/",
        verbose_name="CSV File with Emails",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_external_email_campaigns",
        verbose_name="Created By",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created At",
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name="Sent",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Sent At",
    )

    class Meta:
        verbose_name = "Legacy External Email Campaign"
        verbose_name_plural = "Legacy External Email Campaigns"
        ordering = ["-created_at"]

    def __str__(self):
        return f"External Campaign: {self.title}"


class ExternalContact(models.Model):
    """
    Contact record imported from outside TownLIT.
    """

    email = models.EmailField(
        unique=True,
        verbose_name="Email Address",
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="First Name",
    )
    family = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Last Name",
    )
    gender = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Gender",
    )
    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date of Birth",
    )
    nation = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nationality",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Country of Residence",
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Phone Number",
    )
    recognize = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="How They Recognize TownLIT",
    )
    registre_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Initial Registration Date",
    )

    source_campaign = models.ForeignKey(
        ExternalEmailCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contacts",
        verbose_name="Source Campaign",
    )

    source = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Contact Source",
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tags",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Internal Notes",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata",
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Record Created At",
    )
    last_contacted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Contacted At",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Active",
    )
    is_unsubscribed = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Unsubscribed",
    )
    became_user = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Converted to User",
    )
    became_user_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="User Conversion Date",
    )
    deleted_after_signup = models.BooleanField(
        default=False,
        verbose_name="Deleted After Signup",
    )
    deleted_after_signup_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Deleted After Signup At",
    )

    class Meta:
        verbose_name = "External Contact"
        verbose_name_plural = "External Contacts"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email