# apps/communication/models/base.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


import uuid

from django.db import models
from django.utils import timezone

from apps.communication.constants import EmailBlockType


class CommunicationRecord(models.Model):
    """
    Shared timestamps for communication models.
    """

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created At",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At",
    )

    class Meta:
        abstract = True


class PublicCommunicationRecord(CommunicationRecord):
    """
    Base for new records that need a stable public identifier.
    """

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    class Meta:
        abstract = True


class EmailContentBlockBase(PublicCommunicationRecord):
    """
    Shared content block structure for templates and campaigns.
    """

    block_type = models.CharField(
        max_length=30,
        choices=EmailBlockType.choices,
        verbose_name="Block Type",
    )
    name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Internal Block Name",
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Block Content",
    )
    styles = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Block Styles",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name="Sort Order",
    )
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Enabled",
    )

    class Meta:
        abstract = True
        ordering = ["sort_order", "id"]