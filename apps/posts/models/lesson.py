from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt


from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin
from validators.mediaValidators.audio_validators import validate_audio_file
from validators.mediaValidators.video_validators import validate_video_file
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


    


# Lesson Models ----------------------------------------------------------------------------------------------------------
class Lesson(SlugMixin):
    IMAGE = FileUpload('posts','photos','lesson')
    AUDIO = FileUpload('posts', 'audios', 'lesson')
    VIDEO = FileUpload('posts', 'videos', 'lesson')
    
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=50, verbose_name='Title')
    season = models.IntegerField(null=True, blank=True, verbose_name='Season')
    episode = models.IntegerField(null=True, blank=True, verbose_name='Episode')
    in_town_teachers = models.ManyToManyField('profiles.Member', blank=True, db_index=True, verbose_name='Teacher In TownLIT')
    out_town_teachers = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name='Teacher out TownLIT')
    description = models.CharField(max_length=500, null=True, blank=True, verbose_name='Description')
    
    image = models.ImageField(upload_to=IMAGE.dir_upload, null=True, blank=True, validators=[validate_image_file, validate_image_size, validate_no_executable_file], verbose_name='Image Lesson') # Default needed
    audio = models.FileField(upload_to=AUDIO.dir_upload, null=True, blank=True, validators=[validate_audio_file, validate_no_executable_file], verbose_name='Audio Lesson')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_video_file, validate_no_executable_file], verbose_name='Video Lesson')
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
