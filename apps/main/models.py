import os
from django.conf import settings
from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify

from utils.common.utils import FileUpload
from utils.mixins.media_conversion import MediaConversionMixin
from validators.mediaValidators.video_validators import validate_video_file
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file

from .constants import (
                            TERMS_AND_POLICIES_CHOICES, LOG_ACTION_CHOICES, 
                            POLICY_DISPLAY_LOCATION_CHOICES, FOOTER_COLUMN_CHOICES, DISPLAY_IN_OFFICIAL,
                            USER_FEEDBACK_STATUS_CHOICES
                        )
from .constants import LANGUAGE_CHOICES        
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# TERMS AND POLICY Model ---------------------------------------------------------------------------------------
class TermsAndPolicy(models.Model):
    policy_type = models.CharField(max_length=50, choices=TERMS_AND_POLICIES_CHOICES, verbose_name='Policy Type')
    display_location = models.CharField(max_length=20, choices=POLICY_DISPLAY_LOCATION_CHOICES, default=DISPLAY_IN_OFFICIAL, verbose_name='Display Location')
    footer_column = models.CharField(max_length=10, choices=FOOTER_COLUMN_CHOICES, blank=True, null=True, verbose_name="Footer Column (optional)", help_text="Optional. Only applies if display location is Footer or Both.")
    
    title = models.CharField(max_length=255, verbose_name='Title')
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name='Slug')
    content = RichTextUploadingField(config_name='default', verbose_name='Content')

    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en', verbose_name='Language')
    version_number = models.CharField(max_length=20, default='1.0', verbose_name='Version Number')
    requires_acceptance = models.BooleanField(default=False, verbose_name='Requires Acceptance')

    last_updated = models.DateTimeField(auto_now=True, verbose_name='Last Updated')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Terms and Policy'
        verbose_name_plural = 'Terms and Policies'

    def __str__(self):
        return f"{self.title} ({self.language}) v{self.version_number}"

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
    id = models.BigAutoField(primary_key=True)
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
class UserFeedback(MediaConversionMixin, models.Model):
    SCREENSHOT = FileUpload('main', 'screenshot', 'feedback_screenshots')
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feedbacks', verbose_name='User')
    title = models.CharField(max_length=255, verbose_name='Title')
    content = RichTextUploadingField(config_name='default', verbose_name='Content')
    screenshot = models.FileField(
        upload_to=SCREENSHOT.dir_upload, 
        blank=True, null=True, 
        validators=[validate_image_file, validate_image_size, validate_no_executable_file], 
        verbose_name='Document')
    status = models.CharField(max_length=20, choices=USER_FEEDBACK_STATUS_CHOICES, default='new', verbose_name='Status')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    is_converted = models.BooleanField(default=False)

    media_conversion_config = {
        "screenshot": SCREENSHOT,
    }
    
    class Meta:
        verbose_name = 'User Feedback'
        verbose_name_plural = 'User Feedbacks'
        ordering = ['-created_at']
            
    def save(self, *args, **kwargs):
        is_new = self._state.adding or kwargs.get("force_insert", False)
        super().save(*args, **kwargs)

        if is_new and not getattr(self, "is_converted", False):
            self.convert_uploaded_media_async()

    def __str__(self):
        return f"Feedback from {self.user.username} - {self.title}"

    

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
    

# PRAYER Model -----------------------------------------------------------------------------------------------
class Prayer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='prayers')
    full_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    content = models.TextField(verbose_name="Prayer Request")
    allow_display = models.BooleanField(default=False, help_text="User consent to show this prayer")
    
    admin_response = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='prayer_responses')
    responded_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def has_response(self):
        return bool(self.admin_response and self.responded_by)

    def __str__(self):
        name = self.user or self.full_name or "Guest"
        return f"Prayer by {name} at {self.submitted_at:%Y-%m-%d}"
    
    
# VIDEO CATEGORY Model -----------------------------------------------------------------------------------------
class VideoCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Video Category"
        verbose_name_plural = "Video Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class VideoSeries(models.Model):
    intro_video = models.OneToOneField("OfficialVideo", null=True, blank=True, on_delete=models.SET_NULL, related_name="intro_for_series", verbose_name="Introductory Video")
    title = models.CharField(max_length=200, verbose_name="Series Title")
    description = models.TextField(blank=True, verbose_name="Series Description")
    language = models.CharField(max_length=10, default="en", verbose_name="Language")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name="Slug")
    class Meta:
        verbose_name = "Video Series"
        verbose_name_plural = "Video Series"
        ordering = ["-created_at"]
        
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class OfficialVideo(MediaConversionMixin, models.Model):
    VIDEO = FileUpload('main', 'video', 'official_videos')
    THUMBNAIL = FileUpload('main', 'image', 'official_thumbnails')

    title = models.CharField(max_length=200, verbose_name="Title")
    description = RichTextUploadingField(null=True, blank=True, verbose_name="Description")
    language = models.CharField(max_length=10, default="en", verbose_name="Language")
    category = models.ForeignKey(VideoCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="videos", verbose_name="Category")
    series = models.ForeignKey(VideoSeries, on_delete=models.SET_NULL, null=True, blank=True, related_name="videos", verbose_name="Series")
    
    parent = models.ForeignKey( "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children", verbose_name="Parent Video (if part of a folder/season)")
    
    episode_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Episode Number")
    view_count = models.PositiveIntegerField(default=0, verbose_name="View Count")
    
    video_file = models.FileField(
                        upload_to=VIDEO.dir_upload, 
                        validators=[validate_video_file, validate_no_executable_file], 
                        verbose_name="Video File" )
    thumbnail = models.FileField(
                        upload_to=THUMBNAIL.dir_upload, 
                        validators=[validate_image_file, validate_image_size, validate_no_executable_file], 
                        verbose_name="Thumbnail / Poster")

    is_active = models.BooleanField(default=True, verbose_name="Active")
    publish_date = models.DateTimeField(verbose_name="Publish Date")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name="Slug")
    is_converted = models.BooleanField(default=False)

    # ✅ تنظیم مسیرهای تبدیل برای فایل‌ها
    media_conversion_config = {
        "video_file": VIDEO,
        "thumbnail": THUMBNAIL,
    }
    
    class Meta:
        verbose_name = "Official Video"
        verbose_name_plural = "Official Videos"
        ordering = ['-publish_date', 'episode_number']
        
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        is_new = self._state.adding or kwargs.get("force_insert", False)
        super().save(*args, **kwargs)

        if is_new and not getattr(self, "is_converted", False):
            self.convert_uploaded_media_async()

    def __str__(self):
        return self.title


class VideoViewLog(models.Model):
    video = models.ForeignKey(OfficialVideo, on_delete=models.CASCADE, related_name="view_logs")
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Video View Log"
        verbose_name_plural = "Video View Logs"
        ordering = ['-viewed_at']
