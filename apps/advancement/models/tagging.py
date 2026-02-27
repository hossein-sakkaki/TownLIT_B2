# apps/advancement/models/tagging.py

from django.db import models
import uuid


class TagCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        TagCategory, on_delete=models.PROTECT, related_name="tags", null=True, blank=True
    )
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["category", "name"], name="uniq_tag_category_name")
        ]

    def __str__(self):
        return self.name