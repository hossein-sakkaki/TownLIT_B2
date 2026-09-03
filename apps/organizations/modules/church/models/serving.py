# apps/organizations/modules/church/models/serving.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.constants import OrganizationMembershipStatus
from apps.organizations.modules.church.constants import (
    ChurchServingAssignmentStatus,
    ChurchServingTeamMembershipStatus,
    ChurchServingTeamStatus,
)


class ChurchServingTeam(models.Model):
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
        related_name="serving_teams",
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serving_teams",
    )
    ministry = models.ForeignKey(
        "organizations.ChurchMinistry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serving_teams",
    )

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, allow_unicode=False)
    description = models.CharField(max_length=1500, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ChurchServingTeamStatus.choices,
        default=ChurchServingTeamStatus.ACTIVE,
        db_index=True,
    )
    sort_order = models.PositiveSmallIntegerField(default=100, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Serving Team"
        verbose_name_plural = "Church Serving Teams"
        ordering = ("sort_order", "name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="organizations_church_unique_serving_team_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "sort_order"]),
            models.Index(fields=["campus", "status"]),
            models.Index(fields=["ministry", "status"]),
        ]

    def clean(self):
        super().clean()

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({
                "campus": "Serving team campus must belong to the same Church workspace.",
            })

        if self.ministry_id and self.ministry.workspace_id != self.workspace_id:
            raise ValidationError({
                "ministry": "Serving team ministry must belong to the same Church workspace.",
            })

        if (
            self.ministry_id
            and self.campus_id
            and self.ministry.campus_id
            and self.ministry.campus_id != self.campus_id
        ):
            raise ValidationError({
                "campus": "Serving team campus must match the ministry campus.",
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


class ChurchServingTeamMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    team = models.ForeignKey(
        ChurchServingTeam,
        on_delete=models.CASCADE,
        related_name="members",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="church_serving_team_memberships",
    )

    role_title = models.CharField(max_length=120, null=True, blank=True)
    is_team_lead = models.BooleanField(default=False, db_index=True)
    is_publicly_listed = models.BooleanField(default=False, db_index=True)

    status = models.CharField(
        max_length=20,
        choices=ChurchServingTeamMembershipStatus.choices,
        default=ChurchServingTeamMembershipStatus.ACTIVE,
        db_index=True,
    )
    active_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    joined_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Serving Team Membership"
        verbose_name_plural = "Church Serving Team Memberships"
        ordering = ("-is_team_lead", "joined_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["team", "membership", "active_slot"],
                name="organizations_church_unique_active_serving_team_member",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchServingTeamMembershipStatus.ACTIVE,
                        ended_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServingTeamMembershipStatus.ENDED,
                        ended_at__isnull=False,
                    )
                ),
                name="organizations_church_serving_team_member_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["team", "status", "is_team_lead"]),
            models.Index(fields=["membership", "status"]),
        ]

    def _sync_active_slot(self):
        self.active_slot = (
            1
            if self.status == ChurchServingTeamMembershipStatus.ACTIVE
            else None
        )

    def clean(self):
        super().clean()
        self._sync_active_slot()

        organization_id = self.team.workspace.activation.organization_id

        if self.membership.organization_id != organization_id:
            raise ValidationError({
                "membership": "Serving team members must belong to the same organization.",
            })

        if self.status == ChurchServingTeamMembershipStatus.ACTIVE:
            if self.membership.status != OrganizationMembershipStatus.ACTIVE:
                raise ValidationError({
                    "membership": "Only active organization members can join serving teams.",
                })

    def save(self, *args, **kwargs):
        self.role_title = (
            " ".join(str(self.role_title).split())
            if self.role_title
            else None
        )
        self._sync_active_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"active_slot"}

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.team_id}:{self.membership_id}:{self.status}"


class ChurchServingAssignment(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    service_plan = models.ForeignKey(
        "organizations.ChurchServicePlan",
        on_delete=models.CASCADE,
        related_name="serving_assignments",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="church_serving_assignments",
    )
    team = models.ForeignKey(
        ChurchServingTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )

    role_label = models.CharField(max_length=120)
    context_key = models.CharField(max_length=240, editable=False, db_index=True)

    status = models.CharField(
        max_length=20,
        choices=ChurchServingAssignmentStatus.choices,
        default=ChurchServingAssignmentStatus.INVITED,
        db_index=True,
    )

    invited_at = models.DateTimeField(default=timezone.now, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_serving_assignments_invited",
    )
    responded_at = models.DateTimeField(null=True, blank=True, db_index=True)
    canceled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_serving_assignments_canceled",
    )
    checked_in_at = models.DateTimeField(null=True, blank=True, db_index=True)
    checked_out_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_serving_assignments_completed",
    )

    notes = models.CharField(max_length=1000, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Serving Assignment"
        verbose_name_plural = "Church Serving Assignments"
        ordering = ("service_plan", "team", "role_label", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["service_plan", "membership", "context_key"],
                name="organizations_church_unique_serving_assignment",
            ),
            models.CheckConstraint(
                check=(
                    Q(checked_out_at__isnull=True)
                    | (
                        Q(checked_in_at__isnull=False)
                        & Q(checked_out_at__gt=models.F("checked_in_at"))
                    )
                ),
                name="organizations_church_serving_checkout_window",
            ),
            models.CheckConstraint(
                check=(
                    Q(checked_in_at__isnull=True)
                    | Q(
                        status__in=[
                            ChurchServingAssignmentStatus.CONFIRMED,
                            ChurchServingAssignmentStatus.COMPLETED,
                        ]
                    )
                ),
                name="organizations_church_serving_checkin_status_consistent",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status=ChurchServingAssignmentStatus.INVITED,
                        responded_at__isnull=True,
                        canceled_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServingAssignmentStatus.CONFIRMED,
                        responded_at__isnull=False,
                        canceled_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServingAssignmentStatus.DECLINED,
                        responded_at__isnull=False,
                        canceled_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServingAssignmentStatus.CANCELED,
                        canceled_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status=ChurchServingAssignmentStatus.COMPLETED,
                        canceled_at__isnull=True,
                        completed_at__isnull=False,
                        checked_in_at__isnull=False,
                    )
                ),
                name="organizations_church_serving_assignment_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["service_plan", "status"]),
            models.Index(fields=["membership", "status", "invited_at"]),
            models.Index(fields=["team", "status"]),
        ]

    def _sync_context_key(self):
        team_token = self.team_id or 0
        role_token = "-".join(
            str(self.role_label or "")
            .strip()
            .lower()
            .replace("/", " ")
            .split()
        )
        self.context_key = f"team:{team_token}|role:{role_token}"

    def clean(self):
        super().clean()
        self._sync_context_key()

        workspace = self.service_plan.workspace
        organization_id = workspace.activation.organization_id

        if self.membership.organization_id != organization_id:
            raise ValidationError({
                "membership": "Serving assignments require membership in the same organization.",
            })

        if self.status in {
            ChurchServingAssignmentStatus.INVITED,
            ChurchServingAssignmentStatus.CONFIRMED,
        } and self.membership.status != OrganizationMembershipStatus.ACTIVE:
            raise ValidationError({
                "membership": "Only active organization members can hold active serving assignments.",
            })

        if self.team_id:
            if self.team.workspace_id != workspace.id:
                raise ValidationError({
                    "team": "Serving assignment team must belong to the same Church workspace.",
                })

            if self.status in {
                ChurchServingAssignmentStatus.INVITED,
                ChurchServingAssignmentStatus.CONFIRMED,
            } and not ChurchServingTeamMembership.objects.filter(
                team=self.team,
                membership=self.membership,
                status=ChurchServingTeamMembershipStatus.ACTIVE,
            ).exists():
                raise ValidationError({
                    "membership": "Active team-based serving assignments require active team membership.",
                })

        if not str(self.role_label or "").strip():
            raise ValidationError({
                "role_label": "Serving role label is required.",
            })

        if self.checked_out_at and not self.checked_in_at:
            raise ValidationError({
                "checked_out_at": "Serving checkout requires a prior check-in.",
            })

    def save(self, *args, **kwargs):
        self.role_label = " ".join(str(self.role_label or "").split())
        self.notes = str(self.notes).strip() if self.notes else None
        self._sync_context_key()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "role_label",
                "context_key",
            }

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service_plan_id}:{self.membership_id}:{self.role_label}"
