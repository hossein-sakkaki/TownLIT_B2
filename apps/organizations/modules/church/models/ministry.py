# apps/organizations/modules/church/models/ministry.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus, OrganizationModuleVisibility
from apps.organizations.modules.church.constants import (
    ChurchMinistryMembershipStatus,
    ChurchMinistryParticipationRole,
    ChurchMinistryStatus,
)


class ChurchMinistry(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    workspace = models.ForeignKey(
        "organizations.ChurchWorkspace",
        on_delete=models.CASCADE,
        related_name="ministries",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ministries",
    )

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, allow_unicode=False)
    description = models.CharField(max_length=1500, null=True, blank=True)

    visibility = models.CharField(
        max_length=20,
        choices=OrganizationModuleVisibility.choices,
        default=OrganizationModuleVisibility.PUBLIC,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchMinistryStatus.choices,
        default=ChurchMinistryStatus.ACTIVE,
        db_index=True,
    )

    is_accepting_participants = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Ministry"
        verbose_name_plural = "Church Ministries"
        ordering = ("sort_order", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="organizations_church_unique_ministry_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "visibility"]),
            models.Index(fields=["campus", "status"]),
        ]

    def clean(self):
        super().clean()

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Ministry campus must belong to the same Church workspace.",
            })

    def save(self, *args, **kwargs):
        self.name = " ".join(str(self.name or "").split())
        self.description = (
            str(self.description).strip()
            if self.description
            else None
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.workspace_id}:{self.slug}"


class ChurchMinistryMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    ministry = models.ForeignKey(
        ChurchMinistry,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="church_ministry_memberships",
    )

    participation_role = models.CharField(
        max_length=20,
        choices=ChurchMinistryParticipationRole.choices,
        default=ChurchMinistryParticipationRole.PARTICIPANT,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchMinistryMembershipStatus.choices,
        default=ChurchMinistryMembershipStatus.ACTIVE,
        db_index=True,
    )

    # MySQL-safe uniqueness slot for current participation.
    active_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    joined_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_publicly_listed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Ministry Membership"
        verbose_name_plural = "Church Ministry Memberships"
        ordering = ("-joined_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["ministry", "membership", "active_slot"],
                name="organizations_church_unique_active_ministry_member",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchMinistryMembershipStatus.ACTIVE,
                        ended_at__isnull=True,
                    )
                    | Q(
                        status=ChurchMinistryMembershipStatus.ENDED,
                        ended_at__isnull=False,
                    )
                ),
                name="organizations_church_ministry_member_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["ministry", "status", "participation_role"]),
            models.Index(fields=["membership", "status"]),
        ]

    def _sync_active_slot(self):
        self.active_slot = (
            1
            if self.status == ChurchMinistryMembershipStatus.ACTIVE
            else None
        )

    def clean(self):
        super().clean()
        self._sync_active_slot()

        if (
            self.membership.organization_id
            != self.ministry.workspace.activation.organization_id
        ):
            raise ValidationError({
                "membership": "Church ministry participants must belong to the same organization.",
            })

        if self.status == ChurchMinistryMembershipStatus.ACTIVE:
            if self.membership.status != OrganizationMembershipStatus.ACTIVE:
                raise ValidationError({
                    "membership": "Only active organization members can participate in ministries.",
                })

    def save(self, *args, **kwargs):
        self._sync_active_slot()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "active_slot",
            }
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ministry_id}:{self.membership_id}:{self.status}"
