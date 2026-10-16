# apps/organizations/models/profile.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models

from apps.organizations.constants import (
    OrganizationContactChannel,
    OrganizationMembershipStatus,
    OrganizationRepresentativeStatus,
    OrganizationWeekday,
)
from validators.user_validators import (
    validate_phone_number,
)


class OrganizationContactPoint(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="contact_points",
    )

    channel = models.CharField(
        max_length=20,
        choices=OrganizationContactChannel.choices,
        db_index=True,
    )

    label = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    value = models.CharField(
        max_length=500,
    )

    is_primary = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_public = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "sort_order",
            "id",
        )

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "channel",
                    "value",
                ],
                name="org_contact_unique_value",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "channel",
                    "is_public",
                ],
                name="org_contact_public_idx",
            ),
        ]

    def clean(self):
        super().clean()

        self.value = str(
            self.value or ""
        ).strip()

        self.label = " ".join(
            str(
                self.label or ""
            ).split()
        )

        if not self.value:
            raise ValidationError({
                "value": (
                    "Contact value is required."
                ),
            })

        if (
            self.channel
            == OrganizationContactChannel.EMAIL
        ):
            validate_email(
                self.value
            )

        elif self.channel in {
            OrganizationContactChannel.PHONE,
            OrganizationContactChannel.WHATSAPP,
        }:
            validate_phone_number(
                self.value
            )

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.channel}:"
            f"{self.value}"
        )


class OrganizationBusinessHour(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="business_hours",
    )

    weekday = models.PositiveSmallIntegerField(
        choices=OrganizationWeekday.choices,
        db_index=True,
    )

    opens_at = models.TimeField(
        null=True,
        blank=True,
    )

    closes_at = models.TimeField(
        null=True,
        blank=True,
    )

    is_closed = models.BooleanField(
        default=False,
    )

    is_24_hours = models.BooleanField(
        default=False,
    )

    label = models.CharField(
        max_length=80,
        blank=True,
        default="",
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "weekday",
            "sort_order",
            "id",
        )

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "weekday",
                    "sort_order",
                ],
                name="org_hours_unique_slot",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "weekday",
                ],
                name="org_hours_weekday_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.is_closed
            and self.is_24_hours
        ):
            raise ValidationError(
                "A business-hours entry cannot "
                "be both closed and open 24 hours."
            )

        if (
            self.is_closed
            or self.is_24_hours
        ):
            if (
                self.opens_at is not None
                or self.closes_at is not None
            ):
                raise ValidationError({
                    "opens_at": (
                        "Closed or 24-hour entries "
                        "must not define times."
                    ),
                    "closes_at": (
                        "Closed or 24-hour entries "
                        "must not define times."
                    ),
                })

            return

        if (
            self.opens_at is None
            or self.closes_at is None
        ):
            raise ValidationError({
                "opens_at": (
                    "Opening and closing times "
                    "are required."
                ),
                "closes_at": (
                    "Opening and closing times "
                    "are required."
                ),
            })

        if (
            self.opens_at
            == self.closes_at
        ):
            raise ValidationError({
                "closes_at": (
                    "Opening and closing times "
                    "must be different."
                ),
            })

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.weekday}:"
            f"{self.sort_order}"
        )


class OrganizationRepresentative(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="public_representatives",
    )

    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="public_representative_records",
    )

    role_title = models.CharField(
        max_length=160,
    )

    status = models.CharField(
        max_length=20,
        choices=OrganizationRepresentativeStatus.choices,
        default=OrganizationRepresentativeStatus.PENDING,
        db_index=True,
    )

    is_primary = models.BooleanField(
        default=False,
        db_index=True,
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0,
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_representative_invitations_sent",
    )

    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "-is_primary",
            "sort_order",
            "id",
        )

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "membership",
                ],
                name="org_representative_unique_member",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "organization",
                    "status",
                    "sort_order",
                ],
                name="org_rep_status_idx",
            ),
        ]

    def clean(self):
        super().clean()

        self.role_title = " ".join(
            str(
                self.role_title or ""
            ).split()
        )

        if not self.role_title:
            raise ValidationError({
                "role_title": (
                    "A public role title is required."
                ),
            })

        if (
            self.membership_id
            and self.organization_id
            and self.membership.organization_id
            != self.organization_id
        ):
            raise ValidationError({
                "membership": (
                    "Representative membership must "
                    "belong to this organization."
                ),
            })

        if (
            self.status
            in {
                OrganizationRepresentativeStatus.PENDING,
                OrganizationRepresentativeStatus.ACCEPTED,
            }
            and self.membership_id
            and self.membership.status
            != OrganizationMembershipStatus.ACTIVE
        ):
            raise ValidationError({
                "membership": (
                    "Only an active organization member "
                    "can be a public representative."
                ),
            })

    @property
    def is_publicly_visible(self):
        return bool(
            self.status
            == OrganizationRepresentativeStatus.ACCEPTED
            and self.membership.status
            == OrganizationMembershipStatus.ACTIVE
            and self.membership.member.is_active
            and self.membership.member.user.is_active
        )

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.membership_id}:"
            f"{self.role_title}"
        )