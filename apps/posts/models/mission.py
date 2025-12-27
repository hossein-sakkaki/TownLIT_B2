from django.db import models
from django.utils import timezone

# import subprocess
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from apps.accounts.models import Address
from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# Mission Models --------------------------------------------------------------------------------------------------------
class Mission(SlugMixin):
    IMAGE_OR_VIDEO = FileUpload('posts','image_or_video','mission')
    
    id = models.BigAutoField(primary_key=True)
    image_or_video = models.FileField(upload_to=IMAGE_OR_VIDEO.dir_upload, null=True, blank=True, validators=[validate_image_file, validate_image_size, validate_no_executable_file, validate_no_executable_file], verbose_name='Mission Image/Video')
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
