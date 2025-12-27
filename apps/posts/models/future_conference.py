from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from uuid import uuid4

from apps.accounts.models import Address
from apps.posts.constants import DELIVERY_METHOD_CHOICES
from utils.mixins.slug_mixin import SlugMixin

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# Conferences Future Models --------------------------------------------------------------------------------------------------
class FutureConference(SlugMixin):
    id = models.BigAutoField(primary_key=True)
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
