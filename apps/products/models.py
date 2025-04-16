# from typing import Any, List, Optional, Tuple
from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from django.utils import timezone
from django.core.exceptions import ValidationError

from utils import FileUpload, SlugMixin
from apps.config.constants import SELLING_TYPE_CHOICES
from common.validators import (
                            validate_no_executable_file,
                            validate_image_or_video_file,
                            validate_image_size
                        )



# BRAND Manager --------------------------------------------
class Brand(SlugMixin):
    BRAND_IMAGE = FileUpload('products','images', 'brand')
    
    brand_title = models.CharField(max_length=100, verbose_name='Brand')
    image_name = models.ImageField(upload_to=BRAND_IMAGE.dir_upload, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Product group picture')
    url_name = 'brand_detail'
    
    def get_slug_source(self):
        return self.brand_title
    
    def __str__(self) -> str:
        return self.brand_title

    
# PRODUCT GROUP Manager --------------------------------------------
class ProductGroup(SlugMixin):
    PRODUCT_GROUP_IMAGE = FileUpload('products','images','product_group')
    
    group_title = models.CharField(max_length=100, verbose_name='Product Group Title')
    image_name = models.ImageField(upload_to=PRODUCT_GROUP_IMAGE.dir_upload, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Product Group Picture')
    description = models.TextField(blank=True, verbose_name='Product Group Description')
    group_parent = models.ForeignKey('ProductGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='groups', verbose_name='Parent Product Group')
    
    register_date = models.DateTimeField(auto_now_add=True, verbose_name='Register Date')
    published_date = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    update_date = models.DateTimeField(auto_now=True, verbose_name='Update Date')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    url_name = 'product_group_detail'

    def get_slug_source(self):
        return self.group_title
    
    def __str__(self) -> str:
        return self.group_title

    
# FEATURE Manager PART 1 --------------------------------------------
class Feature(models.Model):
    feature = models.CharField(max_length=50, verbose_name='Feature')
    product_groups = models.ManyToManyField(ProductGroup, related_name='features', verbose_name='Product Group Feature')
    
    def __str__(self) -> str:
        return self.feature
    
    
# PRODUCT Manager --------------------------------------------
class Product(SlugMixin):
    PRODUCT_IMAGE = FileUpload('products','images','product')
    
    product_name = models.CharField(max_length=150, verbose_name='Product Name')
    summary_description = models.TextField(null=True, blank=True, verbose_name='Summary Description')
    description = RichTextUploadingField(config_name='default', blank=True, null=True, verbose_name='Product Description')
    image_name = models.ImageField(upload_to=PRODUCT_IMAGE.dir_upload, validators=[validate_image_or_video_file, validate_no_executable_file], verbose_name='Product Picture')
    
    product_groups = models.ManyToManyField(ProductGroup, related_name='products', verbose_name='Product Group')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, null=True, related_name='brands', verbose_name='Product Brand')
    feature = models.ManyToManyField(Feature, through="ProductFeature")
        
    register_date = models.DateTimeField(auto_now_add=True, verbose_name='Register Date')
    published_date = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    update_date = models.DateTimeField(auto_now=True, verbose_name='Update Date')
    selling_type = models.CharField(max_length=20, choices=SELLING_TYPE_CHOICES, default='for_sale', verbose_name='Selling Type')        
    price = models.DecimalField(default=0, max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Product Price')
    is_active = models.BooleanField(default=True, blank=True, verbose_name='Is Active')
    url_name = 'product_detail'
    
    def get_slug_source(self):
        return self.product_name
    
    def __str__(self) -> str:
        return self.product_name
        

# FEATURE Manager PART 2 --------------------------------------------
class FeatureValue(models.Model):
    value_title = models.CharField(max_length=50, verbose_name='Value Title')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name='values_of_features', verbose_name='Feature')
    
    def __str__(self) -> str:
        return self.value_title

class ProductFeature(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_features', verbose_name='Product Feature')
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, verbose_name='Feature')
    feature_value = models.ForeignKey(FeatureValue, on_delete=models.CASCADE, related_name='feature_of_value', verbose_name='Feature Value')
    
    def __str__(self) -> str:
        return f'{self.product}=>{self.feature}: {self.value}'
    
    
# GALLERY Manager --------------------------------------------
class Gallery(models.Model):
    PRODUCT_IMAGE = FileUpload('products','images','gallery')
    
    product_gallery = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_gallery', verbose_name='Product Gallery')
    image_name = models.ImageField(upload_to=PRODUCT_IMAGE.dir_upload, validators=[validate_image_or_video_file, validate_no_executable_file, validate_image_size], verbose_name='Product Picture')
    
    def clean(self):
        max_images = 6
        current_images = Gallery.objects.filter(product_gallery=self.product_gallery).count()
        if current_images >= max_images:
            raise ValidationError(f'Each product can only have up to {max_images} images in the gallery.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)