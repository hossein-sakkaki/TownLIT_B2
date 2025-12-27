from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from apps.accounts.models import Address
from apps.posts.constants import DELIVERY_METHOD_CHOICES 


from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin

from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


    

# Announcement Models ------------------------------------------------------------------------------------------------------
class Announcement(SlugMixin):
    IMAGE = FileUpload('posts','photos','announcement')
    
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=50, verbose_name='Title')
    description = models.CharField(max_length=500, verbose_name='Description')
    image = models.ImageField(upload_to=IMAGE.dir_upload, validators=[validate_image_file, validate_image_size, validate_no_executable_file], null=True, blank=True, verbose_name='Announcement Image')
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

