# apps/organization_content/models/feed.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

"""A visibility-controlled reference; never duplicates module-specific records."""

import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone


class OrganizationFeedEntry(models.Model):
    class Source(models.TextChoices):
        UPDATE = "update", "Organization Update"
        MODULE = "module", "Module Activity"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="feed_entries"
    )
    source = models.CharField(max_length=12, choices=Source.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    # Supports integer and UUID primary keys in future module implementations.
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey("content_type", "object_id")
    is_pinned = models.BooleanField(default=False)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "content_type", "object_id"],
                name="org_feed_target_once",
            ),
            models.CheckConstraint(
                check=Q(expires_at__isnull=True) | Q(expires_at__gt=models.F("starts_at")),
                name="org_feed_valid_window",
            ),
        ]
        indexes = [models.Index(fields=["organization", "is_active", "starts_at"])]

    def is_in_display_window(self, now=None):
        now = now or timezone.now()
        return (self.is_active and self.starts_at <= now
                and (self.expires_at is None or self.expires_at > now))
