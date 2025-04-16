from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib import messages
# import subprocess
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from uuid import uuid4


from apps.accounts.models import Address
from apps.config.constants import (
                                DAYS_OF_WEEK_CHOICES, FREQUENCY_CHOICES,
                                DELIVERY_METHOD_CHOICES, COPYRIGHT_CHOICES,
                                REACTION_TYPE_CHOICES,
                            )
from apps.config.post_constants import (
                                CHILDREN_EVENT_TYPE_CHOICES, YOUTH_EVENT_TYPE_CHOICES, WOMEN_EVENT_TYPE_CHOICES,
                                MEN_EVENT_TYPE_CHOICES, SERVICE_EVENT_CHOICES, LITERARY_CATEGORY_CHOICES,
                                MEDIA_CONTENT_CHOICES, RESOURCE_TYPE_CHOICES
                            )
from apps.config.organization_constants import (
                                PRICE_TYPE_CHOICES, ORGANIZATION_TYPE_CHOICES, CHRISTIAN_YOUTH_ORGANIZATION,
                                CHRISTIAN_WOMENS_ORGANIZATION, CHRISTIAN_MENS_ORGANIZATION, CHRISTIAN_CHILDRENS_ORGANIZATION,
                            )

from utils import FileUpload, SlugMixin
from common.validators import (
                                validate_image_or_video_file,
                                validate_audio_file,
                                validate_pdf_file,
                                validate_no_executable_file
                            )
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


    
# Reaction Models ---------------------------------------------------------------------------------
class Reaction(models.Model):
    name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_reactions', verbose_name='Name')
    reaction_type = models.CharField(max_length=20, choices=REACTION_TYPE_CHOICES, verbose_name='Reaction Type')
    message = models.CharField(max_length=80, blank=True, null=True, verbose_name='Reaction Message')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Timestamp')
    def __str__(self):
        return f'{self.name.username} reacted with {self.reaction_type}'

    class Meta:
        verbose_name = "_Reaction"
        verbose_name_plural = "_Reactions"
        unique_together = ('name', 'reaction_type', 'content_type', 'object_id')
    
    
# Comment Models ------------------------------------------------------------------------------------------------------------
class Comment(models.Model):
    name = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_comments', verbose_name='Name')
    comment = models.TextField(blank=True, null=True, verbose_name='Comment')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    recomment = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='responses', verbose_name='Recomment')
    
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Time')
    is_active = models.BooleanField(default=True, null=True, blank=True)

    def __str__(self):
        return f"Comment by {self.name.username}"

    class Meta:
        verbose_name = "_Comment"
        verbose_name_plural = "_Comments"
        ordering = ['-published_at']

    def get_absolute_url(self):
        return reverse("comment_detail", kwargs={"pk": self.pk})
    
    
# Resource Models -----------------------------------------------------------------------------------------------------------
class Resource(models.Model):
    RESOURCE_FILE = FileUpload('posts','resource_file','resource')

    resource_name = models.CharField(max_length=255, verbose_name='Resource Name')
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPE_CHOICES, verbose_name='Resource Type')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    resource_file = models.FileField(upload_to=RESOURCE_FILE, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Resource File')
    url = models.URLField(null=True, blank=True, verbose_name='Resource URL')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Uploaded At')
    author = models.CharField(max_length=255, null=True, blank=True, verbose_name='Author/Creator')
    license = models.CharField(max_length=100, null=True, blank=True, verbose_name='License Information')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    def __str__(self):
        return self.resource_name

    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        
    def get_absolute_url(self):
        return reverse("resource_detail", kwargs={"pk": self.pk})


# Service Event Models ------------------------------------------------------------------------------------------------------
class ServiceEvent(SlugMixin):
    BANNER = FileUpload('posts', 'baners', 'service_event')

    organization_type = models.CharField(max_length=50, choices=ORGANIZATION_TYPE_CHOICES, verbose_name='Organization Type')
    event_type = models.CharField(max_length=50, verbose_name='Event Type')
    custom_event_type = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Event Type Name')
    
    event_banner = models.ImageField(upload_to=BANNER.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file], verbose_name='Event Banner')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    contact_information = models.CharField(max_length=255, null=True, blank=True, verbose_name='Contact Information')

    recurring = models.BooleanField(default=False, verbose_name='Is Recurring')
    frequency = models.CharField(max_length=50, null=True, blank=True, choices=FREQUENCY_CHOICES, verbose_name='Frequency')
    event_date = models.DateField(null=True, blank=True, verbose_name='Event Date')
    day_of_week = models.CharField(max_length=9, null=True, blank=True, choices=DAYS_OF_WEEK_CHOICES, verbose_name='Day of Week')
    start_time = models.TimeField(null=True, blank=True, verbose_name='Start Time')
    duration = models.DurationField(null=True, blank=True, verbose_name='Duration')
    additional_notes = models.CharField(max_length=100, null=True, blank=True, verbose_name='Additional Scheduling Notes')
    registration_required = models.BooleanField(default=False, verbose_name='Registration Required')
    registration_link = models.URLField(null=True, blank=True, verbose_name='Registration Link')

    event_method = models.CharField(max_length=10,choices=DELIVERY_METHOD_CHOICES, default='IN_PERSON', verbose_name='Event Method')
    location = models.ForeignKey(Address, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Location')
    event_link = models.URLField(null=True, blank=True, verbose_name='Event Link')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'service_envent_detail' 
        
    def get_event_type_choices(self):
        if self.organization_type == CHRISTIAN_CHILDRENS_ORGANIZATION:
            return CHILDREN_EVENT_TYPE_CHOICES
        if self.organization_type == CHRISTIAN_YOUTH_ORGANIZATION:
            return YOUTH_EVENT_TYPE_CHOICES
        if self.organization_type == CHRISTIAN_WOMENS_ORGANIZATION:
            return WOMEN_EVENT_TYPE_CHOICES
        if self.organization_type == CHRISTIAN_MENS_ORGANIZATION:
            return MEN_EVENT_TYPE_CHOICES
        elif self.organization_type:
            return SERVICE_EVENT_CHOICES
        return []

    def __init__(self, *args, **kwargs):
        super(ServiceEvent, self).__init__(*args, **kwargs)
        self._meta.get_field('event_type').choices = self.get_event_type_choices()

    def __str__(self):
        return self.custom_name

    def save(self, *args, **kwargs):
        if not self.custom_name:
            self.custom_name = self.custom_event_type
        super().save(*args, **kwargs)
        
    def get_slug_source(self):
        return f"{self.custom_event_type}-{str(uuid4())}"

    class Meta:
        verbose_name = "Service Event"
        verbose_name_plural = "Service Events"


# Testimony Models ------------------------------------------------------------------------------------------------------
class Testimony(SlugMixin):
    THUMBNAIL = FileUpload('posts', 'photos', 'testimony')
    AUDIO = FileUpload('posts', 'audios', 'testimony')
    VIDEO = FileUpload('posts', 'videos', 'testimony')
    
    title = models.CharField(max_length=50, verbose_name='Title')
    content = models.TextField(null=True, blank=True, verbose_name='Testimony Content')
    
    audio = models.FileField(upload_to=AUDIO.dir_upload, null=True, blank=True, validators=[validate_audio_file, validate_no_executable_file], verbose_name='Testimony Audio')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Testimony Video')
    thumbnail_1 = models.ImageField(upload_to=THUMBNAIL.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Thumbnail 1')    #نیاز به دیفالت دارد 
    thumbnail_2 = models.ImageField(upload_to=THUMBNAIL.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Thumbnail 2')    #نیاز به دیفالت دارد 
    
    org_tags = models.ManyToManyField('profilesOrg.Organization', blank=True, related_name='tagged_in_testimonies', db_index=True, verbose_name='Organization Tags')
    user_tags = models.ManyToManyField(CustomUser, blank=True, related_name='tagged_in_testimonies', db_index=True, verbose_name='User Tags')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Updated Date')
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'testimony_detail' 

    def save(self, *args, **kwargs):
        if self.pk and self.updated_at is None:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)
        
    def get_slug_source(self):
        return self.title
        
    def __str__(self):
        return f"{self.title}"

    class Meta:
        verbose_name = "Testimony"
        verbose_name_plural = "Testimonies"


# Witness Models -----------------------------------------------------------------------------------------------------------
class Witness(SlugMixin):
    title = models.CharField(max_length=50, null=True, blank=True, verbose_name='Title')
    testimony = models.ManyToManyField(Testimony, related_name='testimony_of_member', verbose_name='Testimony of Witness')
    re_published_at = models.DateTimeField(default=timezone.now, verbose_name='Republished Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'witness_detail' 

    def get_slug_source(self):
        return str(uuid4())
           
    def __str__(self):
        return f"{self.title}"

    class Meta:
        verbose_name = "Witness"
        verbose_name_plural = "Witnesses"


# Moment Models ----------------------------------------------------------------------------------------------------------
class Moment(SlugMixin):
    IMAGE_OR_VIDEO = FileUpload('posts','moment_files','moment')
    
    content = models.TextField(null=True, blank=True, verbose_name='Moment Content')
    moment_file = models.FileField(upload_to=IMAGE_OR_VIDEO.dir_upload, blank=True, null=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Image/Video')

    org_tags = models.ManyToManyField('profilesOrg.Organization', blank=True, related_name='tagged_in_moments', db_index=True, verbose_name='Organization Tags')
    user_tags = models.ManyToManyField(CustomUser, blank=True, related_name='tagged_in_moments', db_index=True, verbose_name='User Tags')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")

    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Updated Date')
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'moment_detail' 

    def save(self, *args, **kwargs):
        if self.pk and self.updated_at is None:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)
    
    def get_slug_source(self):
        return str(uuid4())
        
    def __str__(self):
        return self.content[:50]
    
    class Meta:
        verbose_name = "Moment"
        verbose_name_plural = "Moments"
    
    
# Pray Models ------------------------------------------------------------------------------------------------------------
class Pray(SlugMixin):
    IMAGE = FileUpload('posts','photos','pray')

    title = models.CharField(max_length=50, verbose_name='Pray Title')
    content = models.TextField(verbose_name='Pray Content')
    image = models.ImageField(upload_to=IMAGE.dir_upload, validators=[validate_image_or_video_file], null=True, blank=True, verbose_name='Pray Image')
    parent = models.ForeignKey("Pray", on_delete=models.CASCADE, related_name='sub_prays', blank=True, null=True, verbose_name='Sub Pray')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Updated Date')
    is_accepted = models.BooleanField(default=False, verbose_name='Is Accepted')
    is_rejected = models.BooleanField(default=False, verbose_name='Is Rejected')
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'pray_detail' 
        
    def save(self, *args, **kwargs):
        if self.pk and self.updated_at is None:
            self.updated_at = timezone.now()
        super().save(*args, **kwargs)
        
    def get_slug_source(self):
        return self.title

    class Meta:
        verbose_name = "Pray"
        verbose_name_plural = "Prays"

    def __str__(self):
        return self.title


# Announcement Models ------------------------------------------------------------------------------------------------------
class Announcement(SlugMixin):
    IMAGE = FileUpload('posts','photos','announcement')
    
    title = models.CharField(max_length=50, verbose_name='Title')
    description = models.CharField(max_length=500, verbose_name='Description')
    image = models.ImageField(upload_to=IMAGE.dir_upload, validators=[validate_image_or_video_file], null=True, blank=True, verbose_name='Announcement Image')
    meeting_type = models.CharField(max_length=10,choices=DELIVERY_METHOD_CHOICES, default='IN_PERSON', verbose_name='Meeting Type')
    url_link = models.URLField(max_length=400, null=True, blank=True, verbose_name='Meeting Link')
    link_sticker_text = models.CharField(max_length=50, null=True, blank=True, verbose_name='Link Sticker Text')
    location = models.ForeignKey(Address, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Location')
    to_date = models.DateTimeField(null=True, blank=True, verbose_name='Date of Announcement')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Created Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'announcement_detail' 

    
    def get_slug_source(self):
        return self.title
    
    def __str__(self):
        return f"{self.title}"
    
    def clean(self):
        if self.to_date and self.created_at and self.to_date <= self.created_at:
            raise ValidationError("Date of Announcement must be after Created Date")
        
    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"


# Lesson Models ----------------------------------------------------------------------------------------------------------
class Lesson(SlugMixin):
    IMAGE = FileUpload('posts','photos','lesson')
    AUDIO = FileUpload('posts', 'audios', 'lesson')
    VIDEO = FileUpload('posts', 'videos', 'lesson')
    
    title = models.CharField(max_length=50, verbose_name='Title')
    season = models.IntegerField(null=True, blank=True, verbose_name='Season')
    episode = models.IntegerField(null=True, blank=True, verbose_name='Episode')
    in_town_teachers = models.ManyToManyField('profiles.Member', blank=True, db_index=True, verbose_name='Teacher In TownLIT')
    out_town_teachers = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name='Teacher out TownLIT')
    description = models.CharField(max_length=500, null=True, blank=True, verbose_name='Description')
    
    image = models.ImageField(upload_to=IMAGE.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file], verbose_name='Image Lesson') # Default needed
    audio = models.FileField(upload_to=AUDIO.dir_upload, null=True, blank=True, validators=[validate_audio_file, validate_no_executable_file], verbose_name='Audio Lesson')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Video Lesson')
    parent = models.ForeignKey("Lesson", on_delete=models.CASCADE, related_name='sub_lessons', blank=True, null=True, verbose_name='Sub Lesson')
   
    view = models.PositiveSmallIntegerField(default=0, verbose_name="View Number")
    record_date = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True, verbose_name='Recorde Date')
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'lesson_detail' 
    
    def get_slug_source(self):
        season_str = f"season-{self.season}" if self.season else ""
        episode_str = f"episode-{self.episode}" if self.episode else ""
        return f"{self.title}-{season_str}-{episode_str}"
    
    def __str__(self):
        return f"{self.title}"
    
    class Meta:
        verbose_name = "Lesson"
        verbose_name_plural = "Lessons"
    
# Preach Models ------------------------------------------------------------------------------------------------------------
class Preach(SlugMixin):
    IMAGE = FileUpload('posts','photos','preach')
    VIDEO = FileUpload('posts', 'videos', 'preach')
    
    title = models.CharField(max_length=50, verbose_name='Preach Title')    
    in_town_preacher = models.ForeignKey('profiles.Member', on_delete=models.CASCADE, null=True, blank=True, db_index=True, verbose_name='Preacher In TownLIT')
    out_town_preacher = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name='Preacher out TownLIT')
    
    image = models.ImageField(upload_to=IMAGE.dir_upload, validators=[validate_image_or_video_file], null=True, blank=True, verbose_name='Lesson Image')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Lesson Video')
     
    view = models.PositiveSmallIntegerField(default=0, verbose_name="View Number")
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'preach_detail' 
    
    def get_slug_source(self):
        return self.title
    
    def __str__(self):
        return f"{self.title}"
    
    class Meta:
        verbose_name = "Preach"
        verbose_name_plural = "Preaches"
    
    
# Worship Models ----------------------------------------------------------------------------------------------------------
class Worship(SlugMixin):
    IMAGE = FileUpload('posts','photos','worship')
    AUDIO = FileUpload('posts', 'audios', 'worship')
    VIDEO = FileUpload('posts', 'videos', 'worship')

    title = models.CharField(max_length=50, verbose_name='Worship Title')
    season = models.IntegerField(null=True, blank=True, verbose_name='Season')
    episode = models.IntegerField(null=True, blank=True, verbose_name='Episode')
    sermon = models.CharField(max_length=500, blank=True, null=True, verbose_name='Sermon')
    hymn_lyrics = models.TextField(null=True, blank=True, verbose_name='Hymn Lyrics')
    in_town_leaders = models.ManyToManyField('profiles.Member', blank=True, db_index=True, verbose_name='Leaders In TownLIT')
    out_town_leaders = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name='Leaders out TownLIT')
    worship_resources = models.ManyToManyField(Resource, blank=True, related_name='worship_resources', verbose_name='Worship Resources')

    image = models.ImageField(upload_to=IMAGE.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Worship Image') # Default Image needed
    audio = models.FileField(upload_to=AUDIO.dir_upload, null=True, blank=True, validators=[validate_audio_file, validate_no_executable_file], verbose_name='Worship Audio')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Worship Video')
    parent = models.ForeignKey("Worship", on_delete=models.CASCADE, related_name='sub_worship', blank=True, null=True, verbose_name='Sub Worship')

    view = models.PositiveSmallIntegerField(default=0, verbose_name="View Number")
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'worship_detail' 
    
    def get_slug_source(self):
        season_str = f"season-{self.season}" if self.season else ""
        episode_str = f"episode-{self.episode}" if self.episode else ""
        return f"{self.title}-{season_str}-{episode_str}"
    
    def __str__(self):
        return f"{self.title}"  

    class Meta:
        verbose_name = "Worship"
        verbose_name_plural = "Worships"


# Media Content Models ----------------------------------------------------------------------------------------------------------
class MediaContent(SlugMixin):
    FILE = FileUpload('posts','media_file','media_content')
    
    content_type = models.CharField(max_length=20, choices=MEDIA_CONTENT_CHOICES, verbose_name='Content Type')
    title = models.CharField(max_length=50, verbose_name='Title')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    file = models.FileField(upload_to=FILE.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Media File')
    link = models.URLField(null=True, blank=True, verbose_name='Content Link')
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'media_content_detail' 

    def get_slug_source(self):
        return str(uuid4())
            
    class Meta:
        verbose_name = "Media Content"
        verbose_name_plural = "Media Contents"

    def __str__(self):
        return self.title


# Library Models ------------------------------------------------------------------------------------------------------------
class Library(SlugMixin):
    IMAGE = FileUpload('posts','photos','library')
    FILE = FileUpload('posts', 'pdf', 'library')
    COPY_RIGHT = FileUpload('posts', 'documents', 'library')

    book_name = models.CharField(max_length=100, db_index=True, verbose_name='Name of Book')
    author = models.CharField(max_length=100, db_index=True, verbose_name='Name of Author')
    publisher_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Publisher Name')
    language = models.CharField(max_length=50, verbose_name='Language of Book')
    translation_language = models.CharField(max_length=50, null=True, blank=True, verbose_name='Language Translated')  
    translator = models.CharField(max_length=50, null=True, blank=True, verbose_name='Translator')
    genre_type = models.CharField(max_length=50, choices=LITERARY_CATEGORY_CHOICES, verbose_name='Genre Type')
    
    image = models.ImageField(upload_to=IMAGE.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Book Image')  
    pdf_file = models.FileField(upload_to=FILE.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Book File') 

    license_type = models.CharField(max_length=20, choices=COPYRIGHT_CHOICES, verbose_name='License Type')
    sale_status = models.CharField(max_length=20, choices=PRICE_TYPE_CHOICES, verbose_name='Sale Status')
    license_document = models.FileField(upload_to=COPY_RIGHT.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='License Document')
    is_upcoming = models.BooleanField(default=False, verbose_name='Is Upcoming Release')
    is_downloadable = models.BooleanField(default=False, verbose_name='Is Downloadable')  
    has_print_version = models.BooleanField(default=False, verbose_name='Has Print Version') 
    
    downloaded = models.PositiveSmallIntegerField(default=0, verbose_name="Count of Downloaded")
    published_date = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'library_detail' 

    def get_slug_source(self):
        return f"{self.book_name}-{self.author}"

    def __str__(self):
        return f"{self.book_name}"

    class Meta:
        verbose_name = "Library"
        verbose_name_plural = "Libraries"


# Mission Models --------------------------------------------------------------------------------------------------------
class Mission(SlugMixin):
    IMAGE_OR_VIDEO = FileUpload('posts','image_or_video','mission')
    
    image_or_video = models.FileField(upload_to=IMAGE_OR_VIDEO.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Mission Image/Video')
    mission_name = models.CharField(max_length=255, verbose_name='Mission Name')
    description = models.TextField(null=True, blank=True, verbose_name='Mission Description')
    start_date = models.DateField(default=timezone.now, verbose_name='Start Date')
    end_date = models.DateField(null=True, blank=True, verbose_name='End Date')
    is_ongoing = models.BooleanField(default=True, verbose_name='Is Ongoing')
    location = models.ForeignKey(Address, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Mission Location')
    contact_persons = models.ManyToManyField(CustomUser, blank=True, related_name='mission_contact_persons', verbose_name='Contact Person')
    funding_goal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Funding Goal')
    raised_funds = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Raised Funds')
    funding_link = models.URLField(max_length=255, null=True, blank=True, verbose_name='Funding Link')
    volunteer_opportunities = models.TextField(null=True, blank=True, verbose_name='Volunteer Opportunities')
    mission_report = models.TextField(null=True, blank=True, verbose_name='Mission Report')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'mission_detail' 

    def save(self, *args, **kwargs):
        if self.end_date and self.end_date < timezone.now().date():
            self.is_ongoing = False
        super().save(*args, **kwargs)
    
    def get_slug_source(self):
        formatted_date = str(self.start_date.strftime('%Y-%m-%d'))
        return f"{self.mission_name}-{formatted_date}"

    def __str__(self):
        return self.mission_name

    class Meta:
        verbose_name = "Mission"
        verbose_name_plural = "Missions"


# Conferences Models ------------------------------------------------------------------------------------------------------
class Conference(SlugMixin):
    conference_name = models.CharField(max_length=255, verbose_name='Conference Name')
    workshops = models.ManyToManyField(Lesson, blank=True, related_name='conference_workshops', verbose_name='Workshops')
    conference_resources = models.ManyToManyField(Resource, blank=True, related_name='conference_resources', verbose_name='Conference Resources')
    description = models.TextField(null=True, blank=True, verbose_name='Conference Description')
    
    conference_date = models.DateField(null=True, blank=True, verbose_name='Conference Date')
    conference_time = models.TimeField(null=True, blank=True, verbose_name='Start Time')
    conference_end_date = models.DateField(null=True, blank=True, verbose_name='Conference End Date')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'conference_detail' 

    def get_slug_source(self):
        return f"{self.conference_name}-{str(uuid4())}"
    
    def __str__(self):
        return self.conference_name

    class Meta:
        verbose_name = "Conference"
        verbose_name_plural = "Conferences"


# Conferences Future Models --------------------------------------------------------------------------------------------------
class FutureConference(SlugMixin):
    conference_name = models.CharField(max_length=255, verbose_name='Future Conference Name')
    registration_required = models.BooleanField(default=False, verbose_name='Registration Required')
    delivery_type = models.CharField(max_length=10, choices=DELIVERY_METHOD_CHOICES, default='IN_PERSON', verbose_name='Meeting Type')
    conference_location = models.ForeignKey(Address, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Conference Location')
    registration_link = models.URLField(null=True, blank=True, verbose_name='Registration Link')
    conference_description = models.TextField(null=True, blank=True, verbose_name='Conference Description')

    in_town_speakers = models.ManyToManyField('profiles.Member', blank=True, related_name='conference_speakers', verbose_name='Speaker In TownLIT')
    out_town_speakers = models.CharField(max_length=200, null=True, blank=True, verbose_name='Speaker out TownLIT')
    sponsors = models.ManyToManyField('profilesOrg.Organization', blank=True, related_name='future_conference_sponsors', verbose_name='Sponsors')
    
    conference_date = models.DateField(null=True, blank=True, verbose_name='Conference Date')
    conference_time = models.TimeField(null=True, blank=True, verbose_name='Start Time')
    conference_end_date = models.DateField(null=True, blank=True, verbose_name='Conference End Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'future_conference_detail' 


    def get_slug_source(self):
        return f"{self.conference_name}-{str(uuid4())}"

    def __str__(self):
        return self.conference_name

    class Meta:
        verbose_name = "Future Conference"
        verbose_name_plural = "Future Conferences"
