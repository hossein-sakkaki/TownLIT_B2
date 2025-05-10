from django.db import models
from django.conf import settings
from ckeditor_uploader.fields import RichTextUploadingField

from apps.config.communication_constants import TARGET_GROUP_CHOICES, STATUS_CHOICES, DRAFT, ALL


# EMAIL TEMPLATE Model ----------------------------------------------------------------
class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Template Name")
    subject_template = models.CharField(max_length=255, verbose_name="Subject")
    body_template = RichTextUploadingField(verbose_name="HTML Body")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# EMAIL CAMPAIGN Model ----------------------------------------------------------------
class EmailCampaign(models.Model):
    title = models.CharField(max_length=255)
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
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
    custom_html = RichTextUploadingField(blank=True, verbose_name="Custom Email Body (Optional)")
    subject = models.CharField(max_length=255)
    target_group = models.CharField(max_length=20, choices=TARGET_GROUP_CHOICES, default=ALL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# EMAIL LOG Model ----------------------------------------------------------------------
class EmailLog(models.Model):
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Scheduled: {self.campaign.title} @ {self.run_at}"


# UNSUBSCRIBE USER  Model -------------------------------------------------------------
class UnsubscribedUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, unique=True)
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
