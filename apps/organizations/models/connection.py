# apps/organizations/models/connection.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-29.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.organizations.constants import (
    OrganizationConnectionStatus,
    OrganizationConnectionType,
)


class OrganizationConnection(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="connections",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_connections_v2",
    )

    relationship_type = models.CharField(
        max_length=20,
        choices=OrganizationConnectionType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationConnectionStatus.choices,
        default=OrganizationConnectionStatus.ACTIVE,
        db_index=True,
    )

    # MySQL-safe uniqueness slot for the active relationship.
    active_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    end_reason = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Connection"
        verbose_name_plural = "Organization Connections"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "user",
                    "active_slot",
                ],
                name=(
                    "organizations_unique_active_"
                    "connection_per_user"
                ),
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=OrganizationConnectionStatus.ACTIVE,
                        ended_at__isnull=True,
                    )
                    | Q(
                        status=OrganizationConnectionStatus.ENDED,
                        ended_at__isnull=False,
                    )
                ),
                name=(
                    "organizations_connection_"
                    "end_state_consistent"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "relationship_type",
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "user",
                    "relationship_type",
                    "status",
                ]
            ),
        ]

    def _sync_active_slot(self):
        self.active_slot = (
            1
            if self.status == OrganizationConnectionStatus.ACTIVE
            else None
        )

    def clean(self):
        super().clean()
        self._sync_active_slot()

        if (
            self.relationship_type
            == OrganizationConnectionType.MEMBER
            and not hasattr(self.user, "member_profile")
        ):
            raise ValidationError({
                "relationship_type": (
                    "Only TownLIT Members can have an official "
                    "organization membership connection."
                ),
            })

    def save(self, *args, **kwargs):
        self._sync_active_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("active_slot")
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.user_id}:"
            f"{self.relationship_type}:"
            f"{self.status}"
        )
