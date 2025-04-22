from django.db import models
from django.utils import timezone
from uuid import uuid4
from apps.accounts.models import Address
from utils.common.utils import FileUpload, SlugMixin
from apps.profilesOrg.models import Organization
from apps.products.models import Product
from common.validators import (
                            validate_image_or_video_file,
                            validate_pdf_file,
                            validate_no_executable_file,
                            validate_phone_number
                        )
from apps.config.store_constants import STORE_PRODUCT_CATEGORY_CHOICES, CURRENCY_CHOICES, USD
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# SERVICE CATEGORY Manager ---------------------------------------------------------
class ServiceCategory(models.Model):
    category_name = models.CharField(max_length=50, choices=STORE_PRODUCT_CATEGORY_CHOICES, unique=True, verbose_name='Service Category')
    description = models.CharField(max_length=300, null=True, blank=True, verbose_name='Description')

    def __str__(self):
        return self.get_category_name_display()

# STORE Manager --------------------------------------------------------------------
class Store(SlugMixin):
    LICENSE_UPLOAD = FileUpload('stores', 'files', 'store')
    LOGO_UPLOAD = FileUpload('stores', 'logo', 'store')

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, db_index=True, related_name='store_details', verbose_name='Store Detail')
    custom_service_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='Custom Service Name')
    description = models.TextField(null=True, blank=True, verbose_name='Store Description')
    store_logo = models.ImageField(upload_to=LOGO_UPLOAD.dir_upload, null=True, blank=True, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Store Logo')
    store_phone_number = models.CharField(max_length=20, null=True, blank=True, validators=[validate_phone_number], verbose_name='Store Contact Number')
    store_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, related_name='store_address', verbose_name='Store Address')

    service_categories = models.ManyToManyField(ServiceCategory, blank=True, related_name='stores', verbose_name='Service Categories')
    currency_preference = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=USD, verbose_name='Currency Preference')
    
    license_number = models.CharField(max_length=50, null=True, blank=True, verbose_name='License Number')
    license_expiry_date = models.DateField(null=True, blank=True, verbose_name="License Expiry Date")
    tax_id = models.CharField(max_length=40, null=True, blank=True, verbose_name='Tax Id')
    store_license = models.FileField(upload_to=LICENSE_UPLOAD.dir_upload, validators=[validate_pdf_file, validate_no_executable_file], verbose_name='Store License')
    
    # Financial and sales information
    products = models.ManyToManyField(Product, blank=True, related_name="stores", verbose_name="Products")
    sales_report = models.TextField(null=True, blank=True, verbose_name="Sales Report")
    revenue = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Revenue")
    
    register_date = models.DateField(default=timezone.now, verbose_name='Register Date')
    active_date = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True, verbose_name='Active Date')
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted to Members')
    is_verified = models.BooleanField(default=False, verbose_name='Is Verified')
    is_hidden = models.BooleanField(default=False, verbose_name="Is Hidden")
    is_active = models.BooleanField(default=False, verbose_name="Is Active")
    url_name = 'store_detail' 

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"
    
    def get_slug_source(self):
        return f"{self.organization.org_name}-{str(uuid4())}"
    
    def __str__(self):
        return f"{self.custom_service_name or 'Store'}: {self.organization.org_name}"