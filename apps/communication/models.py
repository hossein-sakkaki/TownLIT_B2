from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils import timezone

from .constants import (
                        TARGET_GROUP_CHOICES, STATUS_CHOICES, DRAFT, ALL_ACTIVE,
                        EMAIL_LAYOUT_CHOICES, LAYOUT_BASE_SITE
                    )
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# EMAIL TEMPLATE Model ----------------------------------------------------------------
class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Template Name")
    layout = models.CharField(
        max_length=30,
        choices=EMAIL_LAYOUT_CHOICES,
        default=LAYOUT_BASE_SITE,
        verbose_name="Layout Template",
        help_text="Choose the layout this template will use when rendered in emails."
    )
    subject_template = models.CharField(max_length=255, verbose_name="Email Subject")
    body_template = RichTextUploadingField(verbose_name="HTML Body Content")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, verbose_name="Created By")
    created_at = models.DateTimeField( default=timezone.now, verbose_name="Created At")

    class Meta:
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


# EMAIL CAMPAIGN Model ----------------------------------------------------------------
class EmailCampaign(models.Model):
    title = models.CharField(max_length=255, verbose_name="Campaign Title")
    recipients = models.ManyToManyField(
        CustomUser,
        blank=True,
        related_name='manual_campaigns',
        verbose_name="Specific Recipients",
        help_text="Optional: Select specific users to send this email to. If filled, target group will be ignored."
    )
    ignore_unsubscribe = models.BooleanField(
        default=False,
        verbose_name="Ignore Unsubscribed Users",
        help_text="If enabled, email will be sent even to users who unsubscribed."
    )
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Email Template")
    custom_html = RichTextUploadingField(blank=True, verbose_name="Custom Email Body (Optional)")
    subject = models.CharField(max_length=255, verbose_name="Email Subject")
    target_group = models.CharField(max_length=50, choices=TARGET_GROUP_CHOICES, default=ALL_ACTIVE, verbose_name="Target Group")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT, verbose_name="Campaign Status")
    scheduled_time = models.DateTimeField(null=True, blank=True, verbose_name="Scheduled Send Time")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, verbose_name="Created By")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created At")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Sent At")

    # Allows admin to send a test email to themselves
    test_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name="Test Email (Optional)",
        help_text="If provided, this email will receive a test message."
    )

    # Optional category for organizing campaigns
    tag = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Campaign Tag",
        help_text="Optional tag for categorizing campaigns (e.g., Christmas 2024)"
    )

    class Meta:
        verbose_name = "Email Campaign"
        verbose_name_plural = "Email Campaigns"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
    

# EMAIL LOG Model ----------------------------------------------------------------------
class EmailLog(models.Model):
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name="email_logs", verbose_name="Email Campaign")
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="User (if registered)")
    email = models.EmailField(verbose_name="Recipient Email")

    sent_at = models.DateTimeField(default=timezone.now, verbose_name="Sent At")
    opened = models.BooleanField(default=False, verbose_name="Email Opened")
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name="Opened At")
    clicked = models.BooleanField(default=False, verbose_name="Link Clicked")
    clicked_at = models.DateTimeField(null=True, blank=True, verbose_name="Clicked At")

    class Meta:
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.email} – {self.campaign.title}"


# SCHEDULE EMAIL Model ----------------------------------------------------------------
class ScheduledEmail(models.Model):
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, verbose_name="Email Campaign")
    run_at = models.DateTimeField(verbose_name="Scheduled Run Time")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, verbose_name="Scheduled By")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created At")
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name="Executed At")
    is_sent = models.BooleanField(default=False, verbose_name="Sent?")

    class Meta:
        verbose_name = "Scheduled Email"
        verbose_name_plural = "Scheduled Emails"
        ordering = ['-run_at']

    def __str__(self):
        return f"Scheduled: {self.campaign.title} @ {self.run_at}"


# UNSUBSCRIBE USER  Model -------------------------------------------------------------
class UnsubscribedUser(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Registered User",
        help_text="If available, refers to a registered user. Otherwise, use 'Email'."
    )
    email = models.EmailField(
        unique=True,
        verbose_name="Email Address",
        help_text="Used for unsubscribed contacts who are not yet registered users."
    )
    unsubscribed_at = models.DateTimeField(default=timezone.now, verbose_name="Unsubscribed At")

    class Meta:
        verbose_name = "Unsubscribed Contact"
        verbose_name_plural = "Unsubscribed Contacts"
        ordering = ["-unsubscribed_at"]

    def __str__(self):
        return self.user.email if self.user else self.email


# DRAFT CAMPAIGN Model ----------------------------------------------------------------
class DraftCampaign(models.Model):
    campaign = models.OneToOneField(EmailCampaign, on_delete=models.CASCADE, related_name='draft', verbose_name="Related Campaign")
    notes = models.TextField(blank=True, verbose_name="Draft Notes")
    last_edited = models.DateTimeField(auto_now=True, verbose_name="Last Edited At")

    class Meta:
        verbose_name = "Draft Campaign"
        verbose_name_plural = "Draft Campaigns"
        ordering = ['-last_edited']

    def __str__(self):
        return f"Draft: {self.campaign.title}"


    
# EXTERNAL EMAIL CAMPAIGN Model -------------------------------------------------------
class ExternalEmailCampaign(models.Model):
    title = models.CharField(max_length=255, verbose_name="Campaign Title")
    subject = models.CharField(max_length=255, verbose_name="Email Subject")
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    html_body = RichTextUploadingField(verbose_name="Custom Email Body (Optional)")
    csv_file = models.FileField(upload_to='external_campaigns/', verbose_name="CSV File with Emails")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Created By"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Created At")
    is_sent = models.BooleanField(default=False, verbose_name="Is Sent")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Sent At")

    def __str__(self):
        return f"External Campaign: {self.title}"


# EXTERNAL CONTACT Model ------------------------------------------------------------
class ExternalContact(models.Model):
    email = models.EmailField(unique=True, verbose_name="Email Address")
    name = models.CharField(max_length=100, blank=True, verbose_name="First Name")
    family = models.CharField(max_length=100, blank=True, verbose_name="Last Name")
    gender = models.CharField(max_length=20, blank=True, verbose_name="Gender")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    nation = models.CharField(max_length=100, blank=True, verbose_name="Nationality")
    country = models.CharField(max_length=100, blank=True, verbose_name="Country of Residence")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Phone Number")
    recognize = models.CharField(max_length=100, blank=True, verbose_name="How They Recognize TownLIT")
    registre_date = models.DateTimeField(null=True, blank=True, verbose_name="Initial Registration Date")
    source_campaign = models.ForeignKey(
        ExternalEmailCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Source Campaign"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Record Created At")
    is_unsubscribed = models.BooleanField(default=False, verbose_name="Unsubscribed?")
    became_user = models.BooleanField(default=False, verbose_name="Converted to User?")
    became_user_at = models.DateTimeField(null=True, blank=True, verbose_name="User Conversion Date")
    deleted_after_signup = models.BooleanField(default=False, verbose_name="Deleted After Signup?")
    deleted_after_signup_at = models.DateTimeField(null=True, blank=True, verbose_name="Deleted After Signup At")

    class Meta:
        verbose_name = "External Contact"
        verbose_name_plural = "External Contacts"
        ordering = ['-created_at']

    def __str__(self):
        return self.email

