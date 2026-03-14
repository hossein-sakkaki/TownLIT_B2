# apps/accounts/models/social.py

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from apps.accounts.constants.social_media import SOCIAL_MEDIA_CHOICES


class SocialMediaType(models.Model):
    name = models.CharField(max_length=20, choices=SOCIAL_MEDIA_CHOICES, unique=True, verbose_name='Social Media Name')
    icon_class = models.CharField(max_length=100, null=True, blank=True, verbose_name='FontAwesome Class')
    icon_svg = models.TextField(null=True, blank=True, verbose_name='SVG Icon Code')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = 'Social Media Type'
        verbose_name_plural = 'Social Media Types'

    def __str__(self):
        return self.name


class SocialMediaLink(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_media_type = models.ForeignKey(
        SocialMediaType,
        on_delete=models.PROTECT,
        related_name='url_links',
        verbose_name='Social Media Type',
    )
    link = models.URLField(max_length=500, verbose_name='URL Link')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="Content Type")
    object_id = models.PositiveIntegerField(verbose_name="Object ID")
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = "URL Link"
        verbose_name_plural = "URL Links"

    def __str__(self):
        return self.link