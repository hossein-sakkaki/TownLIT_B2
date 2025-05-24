from django.db import models
from django.conf import settings
from ckeditor_uploader.fields import RichTextUploadingField

from .constants import (
                        TARGET_GROUP_CHOICES, STATUS_CHOICES, DRAFT, ALL_ACTIVE,
                        EMAIL_LAYOUT_CHOICES, LAYOUT_BASE_SITE
                    )
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


class LongRichTextUploadingField(RichTextUploadingField):
    def db_type(self, connection):
        if connection.vendor == 'mysql':
            return 'LONGTEXT'
        return super().db_type(connection)
    

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
    subject_template = models.CharField(max_length=255, verbose_name="Subject")
    body_template = LongRichTextUploadingField(verbose_name="HTML Body")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# EMAIL CAMPAIGN Model ----------------------------------------------------------------
class EmailCampaign(models.Model):
    title = models.CharField(max_length=255)
    recipients = models.ManyToManyField(
        CustomUser,
        blank=True,
        related_name='manual_campaigns',
        verbose_name='Specific Recipients',
        help_text='Optional: Select specific users to send this email to. If filled, target group will be ignored.'
    )
    ignore_unsubscribe = models.BooleanField(
        default=False,
        verbose_name="Ignore Unsubscribed Users",
        help_text="If enabled, email will be sent even to users who unsubscribed."
    )
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    custom_html = LongRichTextUploadingField(blank=True, verbose_name="Custom Email Body (Optional)")
    subject = models.CharField(max_length=255)
    target_group = models.CharField(max_length=50, choices=TARGET_GROUP_CHOICES, default=ALL_ACTIVE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title
    

# EMAIL LOG Model ----------------------------------------------------------------------
class EmailLog(models.Model):
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name="email_logs")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    email = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)
    opened = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email} - {self.campaign.title}"

# SCHEDULE EMAIL Model ----------------------------------------------------------------
class ScheduledEmail(models.Model):
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE)
    run_at = models.DateTimeField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Scheduled: {self.campaign.title} @ {self.run_at}"


# UNSUBSCRIBE USER  Model -------------------------------------------------------------
class UnsubscribedUser(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    unsubscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.email


# DRAFT CAMPAIGN Model ----------------------------------------------------------------
class DraftCampaign(models.Model):
    campaign = models.OneToOneField(EmailCampaign, on_delete=models.CASCADE, related_name='draft')
    notes = models.TextField(blank=True)
    last_edited = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Draft: {self.campaign.title}"


    
# EXTERNAL EMAIL CAMPAIGN Model -------------------------------------------------------
class ExternalEmailCampaign(models.Model):
    title = models.CharField(max_length=255, verbose_name="Campaign Title")
    subject = models.CharField(max_length=255, verbose_name="Email Subject")
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    html_body = LongRichTextUploadingField(verbose_name="Custom Email Body (Optional)")
    csv_file = models.FileField(upload_to='external_campaigns/', verbose_name="CSV File with Emails")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    is_sent = models.BooleanField(default=False, verbose_name="Is Sent")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Sent At")

    def __str__(self):
        return f"External Campaign: {self.title}"

# EXTERNAL CONTACT Model ------------------------------------------------------------
class ExternalContact(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    family = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    nation = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)  
    phone = models.CharField(max_length=50, blank=True) 
    recognize = models.CharField(max_length=100, blank=True)
    registre_date = models.DateTimeField(null=True, blank=True)
    source_campaign = models.ForeignKey('ExternalEmailCampaign', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_unsubscribed = models.BooleanField(default=False)
    became_user = models.BooleanField(default=False)
    became_user_at = models.DateTimeField(null=True, blank=True)
    deleted_after_signup = models.BooleanField(default=False)
    deleted_after_signup_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "External Contact"
        verbose_name_plural = "External Contacts"

    def __str__(self):
        return self.email
