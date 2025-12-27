from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from uuid import uuid4

from apps.posts.models.common import Resource
from apps.posts.models.lesson import Lesson
from utils.mixins.slug_mixin import SlugMixin

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# Conferences Models ------------------------------------------------------------------------------------------------------
class Conference(SlugMixin):
    id = models.BigAutoField(primary_key=True)
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
