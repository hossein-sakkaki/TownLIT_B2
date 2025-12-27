from django.db import models
from django.utils import timezone

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from uuid import uuid4
from utils.mixins.slug_mixin import SlugMixin
from apps.posts.models.testimony import Testimony

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# Witness Models -----------------------------------------------------------------------------------------------------------
class Witness(SlugMixin):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=50, null=True, blank=True, verbose_name='Title')
    testimony = models.ManyToManyField(Testimony, related_name='testimony_of_member', verbose_name='Testimony of Witness')
    re_published_at = models.DateTimeField(default=timezone.now, verbose_name='Republished Date')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'witness_detail' 

    def get_slug_source(self):
        return str(uuid4())
           
    def __str__(self):
        return f"{self.title}"

    class Meta:
        verbose_name = "Witness"
        verbose_name_plural = "Witnesses"


