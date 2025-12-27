from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin

from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# Pray Models ------------------------------------------------------------------------------------------------------------
class Pray(SlugMixin):
    IMAGE = FileUpload('posts','photos','pray')

    id = models.BigAutoField(primary_key=True)  
    title = models.CharField(max_length=50, verbose_name='Pray Title')
    content = models.TextField(verbose_name='Pray Content')
    image = models.ImageField(upload_to=IMAGE.dir_upload, validators=[validate_image_file, validate_image_size, validate_no_executable_file], null=True, blank=True, verbose_name='Pray Image')
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
