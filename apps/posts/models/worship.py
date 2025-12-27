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
from apps.posts.models.common import Resource
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



    

# Worship Models ----------------------------------------------------------------------------------------------------------
class Worship(SlugMixin):
    IMAGE = FileUpload('posts','photos','worship')
    AUDIO = FileUpload('posts', 'audios', 'worship')
    VIDEO = FileUpload('posts', 'videos', 'worship')

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=50, verbose_name='Worship Title')
    season = models.IntegerField(null=True, blank=True, verbose_name='Season')
    episode = models.IntegerField(null=True, blank=True, verbose_name='Episode')
    sermon = models.CharField(max_length=500, blank=True, null=True, verbose_name='Sermon')
    hymn_lyrics = models.TextField(null=True, blank=True, verbose_name='Hymn Lyrics')
    in_town_leaders = models.ManyToManyField('profiles.Member', blank=True, db_index=True, verbose_name='Leaders In TownLIT')
    out_town_leaders = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name='Leaders out TownLIT')
    worship_resources = models.ManyToManyField(Resource, blank=True, related_name='worship_resources', verbose_name='Worship Resources')

    image = models.ImageField(upload_to=IMAGE.dir_upload, null=True, blank=True, validators=[validate_image_file, validate_image_size, validate_no_executable_file], verbose_name='Worship Image') # Default Image needed
    audio = models.FileField(upload_to=AUDIO.dir_upload, null=True, blank=True, validators=[validate_audio_file, validate_no_executable_file], verbose_name='Worship Audio')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_video_file, validate_no_executable_file], verbose_name='Worship Video')
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

