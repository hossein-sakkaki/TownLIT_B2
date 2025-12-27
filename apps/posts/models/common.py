from django.db import models
from django.utils import timezone
from django.urls import reverse

from apps.accounts.models import Address
from apps.posts.constants import RESOURCE_TYPE_CHOICES
from utils.common.utils import FileUpload
from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.security_validators import validate_no_executable_file

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


    

        

# Resource Models -----------------------------------------------------------------------------------------------------------
class Resource(models.Model):
    RESOURCE_FILE = FileUpload('posts','resource_file','resource')

    resource_name = models.CharField(max_length=255, verbose_name='Resource Name')
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPE_CHOICES, verbose_name='Resource Type')
    description = models.TextField(null=True, blank=True, verbose_name='Description')
    resource_file = models.FileField(upload_to=RESOURCE_FILE, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Resource File')
    url = models.URLField(null=True, blank=True, verbose_name='Resource URL')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Uploaded At')
    author = models.CharField(max_length=255, null=True, blank=True, verbose_name='Author/Creator')
    license = models.CharField(max_length=100, null=True, blank=True, verbose_name='License Information')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    def __str__(self):
        return self.resource_name

    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        
    def get_absolute_url(self):
        return reverse("resource_detail", kwargs={"pk": self.pk})

