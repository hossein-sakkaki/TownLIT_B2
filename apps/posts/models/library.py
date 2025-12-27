from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from apps.accounts.models import Address
from apps.posts.constants import LITERARY_CATEGORY_CHOICES, COPYRIGHT_CHOICES
from apps.profilesOrg.constants import PRICE_TYPE_CHOICES
from utils.common.utils import FileUpload
from utils.mixins.slug_mixin import SlugMixin

from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# Library Models ------------------------------------------------------------------------------------------------------------
class Library(SlugMixin):
    IMAGE = FileUpload('posts','photos','library')
    FILE = FileUpload('posts', 'pdf', 'library')
    COPY_RIGHT = FileUpload('posts', 'documents', 'library')

    id = models.BigAutoField(primary_key=True)
    book_name = models.CharField(max_length=100, db_index=True, verbose_name='Name of Book')
    author = models.CharField(max_length=100, db_index=True, verbose_name='Name of Author')
    publisher_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Publisher Name')
    language = models.CharField(max_length=50, verbose_name='Language of Book')
    translation_language = models.CharField(max_length=50, null=True, blank=True, verbose_name='Language Translated')  
    translator = models.CharField(max_length=50, null=True, blank=True, verbose_name='Translator')
    genre_type = models.CharField(max_length=50, choices=LITERARY_CATEGORY_CHOICES, verbose_name='Genre Type')
    
    image = models.ImageField(upload_to=IMAGE.dir_upload, null=True, blank=True, validators=[validate_image_file, validate_image_size, validate_no_executable_file], verbose_name='Book Image')  
    pdf_file = models.FileField(upload_to=FILE.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Book File') 

    license_type = models.CharField(max_length=20, choices=COPYRIGHT_CHOICES, verbose_name='License Type')
    sale_status = models.CharField(max_length=20, choices=PRICE_TYPE_CHOICES, verbose_name='Sale Status')
    license_document = models.FileField(upload_to=COPY_RIGHT.dir_upload, null=True, blank=True, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='License Document')
    is_upcoming = models.BooleanField(default=False, verbose_name='Is Upcoming Release')
    is_downloadable = models.BooleanField(default=False, verbose_name='Is Downloadable')  
    has_print_version = models.BooleanField(default=False, verbose_name='Has Print Version') 
    
    downloaded = models.PositiveSmallIntegerField(default=0, verbose_name="Count of Downloaded")
    published_date = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'library_detail' 

    def get_slug_source(self):
        return f"{self.book_name}-{self.author}"

    def __str__(self):
        return f"{self.book_name}"

    class Meta:
        verbose_name = "Library"
        verbose_name_plural = "Libraries"
