# apps/accounts/models/labels.py

from django.db import models
from colorfield.fields import ColorField

from apps.accounts.constants.user_labels import USER_LABEL_CHOICES


class CustomLabel(models.Model):
    name = models.CharField(max_length=20, choices=USER_LABEL_CHOICES, unique=True, verbose_name='Label Name')
    color = ColorField(verbose_name='Color Code')
    description = models.CharField(max_length=500, null=True, blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    class Meta:
        verbose_name = "Label"
        verbose_name_plural = "Labels"

    def __str__(self):
        return self.name