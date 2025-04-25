from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify

from apps.config.constants import TERMS_AND_POLICIES_CHOICES, LOG_ACTION_CHOICES, POLICY_DISPLAY_LOCATION_CHOICES, DISPLAY_IN_OFFICIAL
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# TERMS AND POLICY Model ---------------------------------------------------------------------------------------
class TermsAndPolicy(models.Model):
    policy_type = models.CharField(max_length=50, choices=TERMS_AND_POLICIES_CHOICES, verbose_name='Policy Type')
    display_location = models.CharField(max_length=20, choices=POLICY_DISPLAY_LOCATION_CHOICES, default=DISPLAY_IN_OFFICIAL, verbose_name='Display Location')
    title = models.CharField(max_length=255, verbose_name='Title')
    content = RichTextUploadingField(config_name='default', verbose_name='Content')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Last Updated')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name='Slug')

    class Meta:
        verbose_name = 'Terms and Policy'
        verbose_name_plural = 'Terms and Policies'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # If the content has changed, save the previous version to history
        if self.id:
            previous = TermsAndPolicy.objects.get(pk=self.id)
            if previous.content != self.content:
                PolicyChangeHistory.objects.create(
                    policy=self,
                    old_content=previous.content,
                    changed_at=previous.last_updated
                )
        if not self.slug:
            self.slug = slugify(self.policy_type)
        super(TermsAndPolicy, self).save(*args, **kwargs)


# USER AGREEMENT Model ------------------------------------------------------------------------------------------
class UserAgreement(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='agreements', verbose_name='User')
    policy = models.ForeignKey(TermsAndPolicy, on_delete=models.CASCADE, related_name='user_agreements', verbose_name='Policy')
    agreed_at = models.DateTimeField(auto_now_add=True, verbose_name='Agreed At')
    is_latest_agreement = models.BooleanField(default=True, verbose_name='Is Latest Agreement')

    class Meta:
        verbose_name = 'User Agreement'
        verbose_name_plural = 'User Agreements'
        unique_together = ('user', 'policy')

    def __str__(self):
        return f"{self.user.username} agreed to {self.policy.title}"

    def save(self, *args, **kwargs):
        # If a new UserAgreement is being saved, mark previous agreements as not latest
        if self.id is None:
            UserAgreement.objects.filter(user=self.user, is_latest_agreement=True).update(is_latest_agreement=False)
        super(UserAgreement, self).save(*args, **kwargs)


# POLICY CHANGE HISTORY Model -----------------------------------------------------------------------------------
class PolicyChangeHistory(models.Model):
    policy = models.ForeignKey(TermsAndPolicy, on_delete=models.CASCADE, related_name='change_history', verbose_name='Policy')
    old_content = RichTextUploadingField(config_name='default', verbose_name='Old Content')
    changed_at = models.DateTimeField(verbose_name='Changed At')

    class Meta:
        verbose_name = 'Policy Change History'
        verbose_name_plural = 'Policy Change Histories'
        ordering = ['-changed_at']

    def __str__(self):
        return f"Change for {self.policy.title} at {self.changed_at}"

# FAQ Model -----------------------------------------------------------------------------------------------------
class FAQ(models.Model):
    question = RichTextUploadingField(config_name='default', verbose_name='Question')
    answer = RichTextUploadingField(config_name='default', verbose_name='Answer')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Last Updated')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question


# USER FEEDBACK Model -------------------------------------------------------------------------------------------
class UserFeedback(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feedbacks', verbose_name='User')
    title = models.CharField(max_length=255, verbose_name='Title')
    content = RichTextUploadingField(config_name='default', verbose_name='Content')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')

    # Fields for GenericForeignKey
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    feedback_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = 'User Feedback'
        verbose_name_plural = 'User Feedbacks'

    def __str__(self):
        return f"Feedback from {self.user.username}"
    

# SITE ANNOUNCEMENT Model -------------------------------------------------------------------------------------------
class SiteAnnouncement(models.Model):
    title = models.CharField(max_length=255, verbose_name='Title')
    content = RichTextUploadingField(config_name='default', verbose_name='Content')
    publish_date = models.DateTimeField(verbose_name='Publish Date')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Site Announcement'
        verbose_name_plural = 'Site Announcements'

    def __str__(self):
        return self.title


# USER ACTION LOG Model ----------------------------------------------------------------------------------------
class UserActionLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='action_logs', verbose_name='User')
    action_type = models.CharField(max_length=10, choices=LOG_ACTION_CHOICES, verbose_name='Action Type')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name='Target Model')
    object_id = models.PositiveIntegerField(verbose_name='Target Instance ID')
    target_object = GenericForeignKey('content_type', 'object_id')
    action_timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Action Timestamp')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Address')
    user_agent = models.CharField(max_length=255, null=True, blank=True, verbose_name='User Agent')

    class Meta:
        verbose_name = 'User Action Log'
        verbose_name_plural = 'User Action Logs'
        ordering = ['-action_timestamp']

    def __str__(self):
        return f"{self.user.username} performed {self.get_action_type_display()} on {self.content_type} (ID: {self.object_id})"