from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from uuid import uuid4

from apps.posts.constants import MEDIA_CONTENT_CHOICES
from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin
from validators.mediaValidators.pdf_validators import validate_pdf_file

from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# Media Content Models ----------------------------------------------------------------------------------------------------------
class MediaContent(SlugMixin):
    FILE = FileUpload('posts','media_file','media_content')
    
    id = models.BigAutoField(primary_key=True)
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
