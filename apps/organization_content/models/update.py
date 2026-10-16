# apps/organization_content/models/update.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

"""Organization-owned standalone public updates. Not a Church or Event model."""

import uuid
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class OrganizationUpdate(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="public_updates"
    )
    caption = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    # Reuse the existing cross-content interaction tables; do not duplicate them.
    reactions = GenericRelation(
        "posts.Reaction", content_type_field="content_type", object_id_field="object_id"
    )
    comments = GenericRelation(
        "posts.Comment", content_type_field="content_type", object_id_field="object_id"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="organization_updates_created",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="organization_updates_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "status", "published_at"])]

    def clean(self):
        super().clean()
        if not (self.caption or "").strip():
            raise ValidationError({"caption": "Caption is required."})
        if self.status == self.Status.PUBLISHED and not self.published_at:
            raise ValidationError({"published_at": "Published updates need a timestamp."})
        if self.status == self.Status.ARCHIVED and not self.archived_at:
            raise ValidationError({"archived_at": "Archived updates need a timestamp."})

    @property
    def is_publicly_available(self):
        return (self.status == self.Status.PUBLISHED
                and self.organization.status == "active"
                and self.organization.visibility == "public"
                and self.published_at is not None
                and self.published_at <= timezone.now())


class OrganizationUpdateMedia(models.Model):
    update = models.ForeignKey(
        OrganizationUpdate, on_delete=models.CASCADE, related_name="media_items"
    )
    asset = models.ForeignKey(
        "organization_media.OrganizationMediaAsset", on_delete=models.PROTECT,
        related_name="update_usages",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["update", "asset"], name="org_update_media_unique")]
        ordering = ("sort_order", "id")

    def clean(self):
        super().clean()
        if self.asset_id and self.update_id:
            if self.asset.organization_id != self.update.organization_id:
                raise ValidationError("Update and media asset must belong to the same Organization.")
