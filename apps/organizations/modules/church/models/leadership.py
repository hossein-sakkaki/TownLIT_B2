# apps/organizations/modules/church/models/leadership.py
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

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchLeadershipAssignmentStatus,
    ChurchLeadershipPositionType,
)


class ChurchLeadershipAssignment(models.Model):
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
        related_name="leadership_assignments",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="church_leadership_assignments",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leadership_assignments",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leadership_assignments",
    )

    position_type = models.CharField(
        max_length=30,
        choices=ChurchLeadershipPositionType.choices,
        db_index=True,
    )
    custom_title = models.CharField(max_length=160, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=ChurchLeadershipAssignmentStatus.choices,
        default=ChurchLeadershipAssignmentStatus.ACTIVE,
        db_index=True,
    )

    # Normalized scope avoids nullable-key uniqueness gaps on MySQL.
    context_key = models.CharField(
        max_length=120,
        editable=False,
        db_index=True,
    )
    active_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    publicly_listed = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=100, db_index=True)

    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Leadership Assignment"
        verbose_name_plural = "Church Leadership Assignments"
        ordering = ("sort_order", "position_type", "id")
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workspace",
                    "membership",
                    "position_type",
                    "context_key",
                    "active_slot",
                ],
                name="organizations_church_unique_active_leadership",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchLeadershipAssignmentStatus.ACTIVE,
                        ended_at__isnull=True,
                    )
                    | Q(
                        status=ChurchLeadershipAssignmentStatus.ENDED,
                        ended_at__isnull=False,
                    )
                ),
                name="organizations_church_leadership_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "position_type"]),
            models.Index(fields=["membership", "status"]),
            models.Index(fields=["campus", "status"]),
            models.Index(fields=["ministry", "status"]),
        ]

    def _sync_derived_fields(self):
        campus_token = self.campus_id or 0
        ministry_token = self.ministry_id or 0
        self.context_key = f"campus:{campus_token}|ministry:{ministry_token}"
        self.active_slot = (
            1
            if self.status == ChurchLeadershipAssignmentStatus.ACTIVE
            else None
        )

    def clean(self):
        super().clean()
        self._sync_derived_fields()

        organization_id = self.workspace.activation.organization_id

        if self.membership.organization_id != organization_id:
            raise ValidationError({
                "membership": "Church leaders must be official members of the same organization.",
            })

        if self.status == ChurchLeadershipAssignmentStatus.ACTIVE:
            if self.membership.status != OrganizationMembershipStatus.ACTIVE:
                raise ValidationError({
                    "membership": "Only active organization members can hold active leadership positions.",
                })

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Leadership campus must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != self.workspace_id:
            raise ValidationError({
                "ministry": "Leadership ministry must belong to the same Church workspace.",
            })

        if (
            self.ministry_id
            and self.campus_id
            and self.ministry.campus_id
            and self.ministry.campus_id != self.campus_id
        ):
            raise ValidationError({
                "campus": "Leadership campus must match the ministry campus.",
            })

        if (
            self.position_type == ChurchLeadershipPositionType.OTHER
            and not str(self.custom_title or "").strip()
        ):
            raise ValidationError({
                "custom_title": "Custom title is required for an 'Other' leadership position.",
            })

    def save(self, *args, **kwargs):
        self.custom_title = (
            " ".join(str(self.custom_title).split())
            if self.custom_title
            else None
        )
        self._sync_derived_fields()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "context_key",
                "active_slot",
            }

        return super().save(*args, **kwargs)

    @property
    def effective_title(self) -> str:
        if self.custom_title:
            return self.custom_title
        return self.get_position_type_display()

    def __str__(self):
        return f"{self.workspace_id}:{self.membership_id}:{self.effective_title}"
