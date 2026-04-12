# apps/bookstore_inventory/models/base.py

from django.db import models


class TimeStampedModel(models.Model):
    # Common timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True