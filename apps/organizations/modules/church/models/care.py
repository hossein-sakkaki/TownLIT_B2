# apps/organizations/modules/church/models/care.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.modules.church.constants import (
    ChurchPastoralCareAssignmentRole,
    ChurchPastoralCareAssignmentStatus,
    ChurchPastoralCareCaseStatus,
    ChurchPastoralCareCategory,
    ChurchPastoralCareContactType,
    ChurchPastoralCareNoteType,
    ChurchPastoralCareNoteVisibility,
    ChurchPastoralCareSensitivity,
)


class ChurchPastoralCareCase(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    workspace = models.ForeignKey(
        "organizations.ChurchWorkspace",
        on_delete=models.CASCADE,
        related_name="pastoral_care_cases",
    )
    congregant = models.ForeignKey(
        "organizations.ChurchCongregant",
        on_delete=models.PROTECT,
        related_name="pastoral_care_cases",
    )

    category = models.CharField(
        max_length=32,
        choices=ChurchPastoralCareCategory.choices,
        default=ChurchPastoralCareCategory.GENERAL,
        db_index=True,
    )
    sensitivity = models.CharField(
        max_length=32,
        choices=ChurchPastoralCareSensitivity.choices,
        default=ChurchPastoralCareSensitivity.STANDARD,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchPastoralCareCaseStatus.choices,
        default=ChurchPastoralCareCaseStatus.OPEN,
        db_index=True,
    )

    title = models.CharField(max_length=180)
    summary_encrypted = models.TextField(blank=True, default="")

    opened_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_church_pastoral_care_cases",
    )
    closed_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_church_pastoral_care_cases",
    )

    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closure_summary_encrypted = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Pastoral Care Case"
        verbose_name_plural = "Church Pastoral Care Cases"
        ordering = ("-opened_at", "-id")
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(status=ChurchPastoralCareCaseStatus.CLOSED, closed_at__isnull=False)
                    | Q(status__in=[ChurchPastoralCareCaseStatus.OPEN, ChurchPastoralCareCaseStatus.ON_HOLD], closed_at__isnull=True)
                ),
                name="organizations_church_pastoral_case_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "sensitivity", "opened_at"]),
            models.Index(fields=["congregant", "status", "opened_at"]),
            models.Index(fields=["workspace", "category", "status"]),
        ]

    def clean(self):
        super().clean()
        if self.congregant.workspace_id != self.workspace_id:
            raise ValidationError({"congregant": "Pastoral care case must belong to the same Church workspace."})
        if self.opened_by_membership_id and self.opened_by_membership.organization_id != self.workspace.activation.organization_id:
            raise ValidationError({"opened_by_membership": "Opening membership must belong to the same Organization."})
        if self.closed_by_membership_id and self.closed_by_membership.organization_id != self.workspace.activation.organization_id:
            raise ValidationError({"closed_by_membership": "Closing membership must belong to the same Organization."})
        if self.status == ChurchPastoralCareCaseStatus.CLOSED and not self.closed_at:
            raise ValidationError({"closed_at": "Closed pastoral care cases require a close timestamp."})
        if self.status != ChurchPastoralCareCaseStatus.CLOSED and self.closed_at:
            raise ValidationError({"closed_at": "Open pastoral care cases cannot have a close timestamp."})

    def __str__(self):
        return f"{self.workspace_id}:{self.public_id}:{self.status}"


class ChurchPastoralCareAssignment(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    case = models.ForeignKey(
        ChurchPastoralCareCase,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_pastoral_care_assignments",
    )
    role = models.CharField(
        max_length=20,
        choices=ChurchPastoralCareAssignmentRole.choices,
        default=ChurchPastoralCareAssignmentRole.SUPPORT,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchPastoralCareAssignmentStatus.choices,
        default=ChurchPastoralCareAssignmentStatus.ACTIVE,
        db_index=True,
    )
    active_slot = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)

    assigned_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Pastoral Care Assignment"
        verbose_name_plural = "Church Pastoral Care Assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["case", "membership", "active_slot"],
                name="organizations_church_unique_active_pastoral_assignment",
            ),
            models.CheckConstraint(
                check=(
                    Q(status=ChurchPastoralCareAssignmentStatus.ACTIVE, ended_at__isnull=True)
                    | Q(status=ChurchPastoralCareAssignmentStatus.ENDED, ended_at__isnull=False)
                ),
                name="organizations_church_pastoral_assignment_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["case", "status", "role"]),
            models.Index(fields=["membership", "status", "assigned_at"]),
        ]

    def _sync_active_slot(self):
        self.active_slot = 1 if self.status == ChurchPastoralCareAssignmentStatus.ACTIVE else None

    def clean(self):
        super().clean()
        self._sync_active_slot()
        if self.membership_id and self.membership.organization_id != self.case.workspace.activation.organization_id:
            raise ValidationError({"membership": "Pastoral care assignee must belong to the same Organization."})
        if self.status == ChurchPastoralCareAssignmentStatus.ACTIVE and not self.membership_id:
            raise ValidationError({"membership": "Active pastoral care assignments require a membership."})

    def save(self, *args, **kwargs):
        self._sync_active_slot()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("active_slot")
            kwargs["update_fields"] = list(update_fields)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.case_id}:{self.membership_id}:{self.status}"


class ChurchPastoralCareNote(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    case = models.ForeignKey(
        ChurchPastoralCareCase,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    author_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_pastoral_care_notes",
    )
    note_type = models.CharField(
        max_length=20,
        choices=ChurchPastoralCareNoteType.choices,
        default=ChurchPastoralCareNoteType.GENERAL,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=24,
        choices=ChurchPastoralCareNoteVisibility.choices,
        default=ChurchPastoralCareNoteVisibility.CASE_TEAM,
        db_index=True,
    )
    body_encrypted = models.TextField()

    # Notes are append-only. Corrections are represented as addenda.
    amends_note = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="addenda",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Church Pastoral Care Note"
        verbose_name_plural = "Church Pastoral Care Notes"
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=["case", "visibility", "created_at"]),
            models.Index(fields=["author_membership", "created_at"]),
        ]

    def clean(self):
        super().clean()
        if not (self.body_encrypted or "").strip():
            raise ValidationError({"body_encrypted": "Encrypted pastoral care note body is required."})
        if self.author_membership_id and self.author_membership.organization_id != self.case.workspace.activation.organization_id:
            raise ValidationError({"author_membership": "Pastoral care note author must belong to the same Organization."})
        if self.amends_note_id and self.amends_note.case_id != self.case_id:
            raise ValidationError({"amends_note": "Pastoral care note addenda must amend a note from the same case."})

    def __str__(self):
        return f"{self.case_id}:{self.note_type}:{self.created_at}"


class ChurchPastoralCareContact(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    case = models.ForeignKey(
        ChurchPastoralCareCase,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    actor_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_pastoral_care_contacts",
    )
    contact_type = models.CharField(
        max_length=24,
        choices=ChurchPastoralCareContactType.choices,
        db_index=True,
    )
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    summary_encrypted = models.TextField(blank=True, default="")
    follow_up_required = models.BooleanField(default=False, db_index=True)
    follow_up_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Church Pastoral Care Contact"
        verbose_name_plural = "Church Pastoral Care Contacts"
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(follow_up_required=True)
                    | Q(follow_up_due_at__isnull=True)
                ),
                name="organizations_church_pastoral_contact_followup_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["case", "occurred_at", "contact_type"]),
            models.Index(fields=["follow_up_required", "follow_up_due_at"]),
        ]

    def clean(self):
        super().clean()
        if self.actor_membership_id and self.actor_membership.organization_id != self.case.workspace.activation.organization_id:
            raise ValidationError({"actor_membership": "Pastoral care contact actor must belong to the same Organization."})
        if self.follow_up_due_at and not self.follow_up_required:
            raise ValidationError({"follow_up_due_at": "A follow-up due date requires follow_up_required=True."})
        if self.follow_up_due_at and self.follow_up_due_at < self.occurred_at:
            raise ValidationError({"follow_up_due_at": "Follow-up due date cannot be before the contact time."})

    def __str__(self):
        return f"{self.case_id}:{self.contact_type}:{self.occurred_at}"
