from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin


from validators.mediaValidators.video_validators import validate_video_file
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# Preach Models ------------------------------------------------------------------------------------------------------------
class Preach(SlugMixin):
    IMAGE = FileUpload('posts','photos','preach')
    VIDEO = FileUpload('posts', 'videos', 'preach')
    
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=50, verbose_name='Preach Title')    
    in_town_preacher = models.ForeignKey('profiles.Member', on_delete=models.CASCADE, null=True, blank=True, db_index=True, verbose_name='Preacher In TownLIT')
    out_town_preacher = models.CharField(max_length=200, null=True, blank=True, db_index=True, verbose_name='Preacher out TownLIT')
    
    image = models.ImageField(upload_to=IMAGE.dir_upload, validators=[validate_image_file, validate_image_size, validate_no_executable_file], null=True, blank=True, verbose_name='Lesson Image')
    video = models.FileField(upload_to=VIDEO.dir_upload, null=True, blank=True, validators=[validate_video_file, validate_no_executable_file], verbose_name='Lesson Video')
     
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