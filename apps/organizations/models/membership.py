# apps/organizations/models/membership.py
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
from django.utils import timezone

from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
    MembershipRequestDirection,
    MembershipRequestStatus,
    OrganizationConnectionType,
    OrganizationMembershipStatus,
)


class OrganizationMembershipRequest(models.Model):
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
        related_name="membership_requests",
    )
    member = models.ForeignKey(
        "profiles.Member",
        on_delete=models.CASCADE,
        related_name="organization_membership_requests_v2",
    )

    direction = models.CharField(
        max_length=30,
        choices=MembershipRequestDirection.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=MembershipRequestStatus.choices,
        default=MembershipRequestStatus.PENDING,
        db_index=True,
    )

    # MySQL-safe uniqueness slot for a pending request.
    pending_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_organization_membership_requests",
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responded_organization_membership_requests",
    )

    message = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    response_message = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Membership Request"
        verbose_name_plural = "Organization Membership Requests"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "member",
                    "pending_slot",
                ],
                name=(
                    "organizations_unique_pending_"
                    "membership_request"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "status",
                    "direction",
                ]
            ),
            models.Index(
                fields=[
                    "member",
                    "status",
                ]
            ),
        ]

    def _sync_pending_slot(self):
        self.pending_slot = (
            1
            if self.status == MembershipRequestStatus.PENDING
            else None
        )

    def clean(self):
        super().clean()
        self._sync_pending_slot()

        if (
            self.direction
            == MembershipRequestDirection.MEMBER_TO_ORGANIZATION
            and self.initiated_by_id
            and self.initiated_by_id != self.member.user_id
        ):
            raise ValidationError({
                "initiated_by": (
                    "Member-initiated requests must be initiated "
                    "by the member account."
                ),
            })

        if (
            self.expires_at
            and self.created_at
            and self.expires_at <= self.created_at
        ):
            raise ValidationError({
                "expires_at": (
                    "Request expiry must be after creation."
                ),
            })

    def save(self, *args, **kwargs):
        self._sync_pending_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("pending_slot")
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return bool(
            self.expires_at
            and self.expires_at <= timezone.now()
        )

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.member_id}:"
            f"{self.direction}:"
            f"{self.status}"
        )


class OrganizationMembership(models.Model):
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
        related_name="memberships",
    )
    member = models.ForeignKey(
        "profiles.Member",
        on_delete=models.CASCADE,
        related_name="organization_membership_records_v2",
    )
    connection = models.OneToOneField(
        "organizations.OrganizationConnection",
        on_delete=models.PROTECT,
        related_name="membership",
    )

    source_request = models.ForeignKey(
        OrganizationMembershipRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_memberships",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_organization_memberships",
    )

    status = models.CharField(
        max_length=20,
        choices=OrganizationMembershipStatus.choices,
        default=OrganizationMembershipStatus.ACTIVE,
        db_index=True,
    )

    # MySQL-safe uniqueness slot for a current membership.
    current_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    joined_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
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
        verbose_name = "Organization Membership"
        verbose_name_plural = "Organization Memberships"
        ordering = ("-joined_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "member",
                    "current_slot",
                ],
                name=(
                    "organizations_unique_current_"
                    "membership"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "status",
                    "joined_at",
                ]
            ),
            models.Index(
                fields=[
                    "member",
                    "status",
                ]
            ),
        ]

    def _sync_current_slot(self):
        self.current_slot = (
            1
            if self.status in CURRENT_MEMBERSHIP_STATUSES
            else None
        )

    def clean(self):
        super().clean()
        self._sync_current_slot()

        if self.connection.organization_id != self.organization_id:
            raise ValidationError({
                "connection": (
                    "Membership connection must belong to the same organization."
                ),
            })

        if self.connection.user_id != self.member.user_id:
            raise ValidationError({
                "connection": (
                    "Membership connection must belong to the same member user."
                ),
            })

        if (
            self.connection.relationship_type
            != OrganizationConnectionType.MEMBER
        ):
            raise ValidationError({
                "connection": (
                    "Official memberships require a member connection."
                ),
            })

    def save(self, *args, **kwargs):
        self._sync_current_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("current_slot")
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    @property
    def is_current(self) -> bool:
        return self.status in CURRENT_MEMBERSHIP_STATUSES

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.member_id}:"
            f"{self.status}"
        )
