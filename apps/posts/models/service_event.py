from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from uuid import uuid4
from apps.accounts.models import Address
from apps.posts.constants import (
                    CHILDREN_EVENT_TYPE_CHOICES, YOUTH_EVENT_TYPE_CHOICES, WOMEN_EVENT_TYPE_CHOICES,
                    MEN_EVENT_TYPE_CHOICES, SERVICE_EVENT_CHOICES, 
                    DAYS_OF_WEEK_CHOICES, FREQUENCY_CHOICES,
                    DELIVERY_METHOD_CHOICES
                )
from apps.profilesOrg.constants import (
                                ORGANIZATION_TYPE_CHOICES, CHRISTIAN_YOUTH_ORGANIZATION,
                                CHRISTIAN_WOMENS_ORGANIZATION, CHRISTIAN_MENS_ORGANIZATION, CHRISTIAN_CHILDRENS_ORGANIZATION,
                            )

from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


    


# Service Event Models ------------------------------------------------------------------------------------------------------
class ServiceEvent(SlugMixin):
    BANNER = FileUpload('posts', 'baners', 'service_event')

    organization_type = models.CharField(max_length=50, choices=ORGANIZATION_TYPE_CHOICES, verbose_name='Organization Type')
    event_type = models.CharField(max_length=50, verbose_name='Event Type')
    custom_event_type = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Event Type Name')
    
    event_banner = models.ImageField(upload_to=BANNER.dir_upload, null=True, blank=True, validators=[validate_image_file, validate_image_size, validate_no_executable_file], verbose_name='Event Banner')
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