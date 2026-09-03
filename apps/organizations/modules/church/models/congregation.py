# apps/organizations/modules/church/models/congregation.py
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

from apps.organizations.constants import ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES
from apps.organizations.modules.church.constants import (
    ChurchCongregantSource,
    ChurchCongregantStatus,
    ChurchDirectoryVisibility,
    ChurchHouseholdMembershipStatus,
    ChurchHouseholdRelationship,
    ChurchHouseholdStatus,
)


class ChurchCongregant(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    workspace = models.ForeignKey(
        "organizations.ChurchWorkspace",
        on_delete=models.CASCADE,
        related_name="congregants",
    )

    # A congregant can be backed by a Member, GuestUser, or a local-only record.
    # Account contact credentials are intentionally never copied here.
    member = models.ForeignKey(
        "profiles.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_congregant_records",
    )
    guest_profile = models.ForeignKey(
        "profiles.GuestUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_congregant_records",
    )
    official_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_congregant_records",
    )

    # Historical fallback only. Live account-backed display names are resolved dynamically.
    display_name_snapshot = models.CharField(max_length=160)
    preferred_name = models.CharField(max_length=80, blank=True, default="")

    status = models.CharField(
        max_length=20,
        choices=ChurchCongregantStatus.choices,
        default=ChurchCongregantStatus.ATTENDEE,
        db_index=True,
    )
    source = models.CharField(
        max_length=24,
        choices=ChurchCongregantSource.choices,
        default=ChurchCongregantSource.STAFF_CREATED,
        db_index=True,
    )
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="congregants",
    )

    directory_visibility = models.CharField(
        max_length=30,
        choices=ChurchDirectoryVisibility.choices,
        default=ChurchDirectoryVisibility.STAFF_ONLY,
        db_index=True,
    )
    directory_consent_at = models.DateTimeField(null=True, blank=True, db_index=True)

    first_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_church_congregants",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_church_congregants",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Congregant"
        verbose_name_plural = "Church Congregants"
        ordering = ("display_name_snapshot", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "member"],
                name="organizations_church_unique_member_congregant",
            ),
            models.UniqueConstraint(
                fields=["workspace", "guest_profile"],
                name="organizations_church_unique_guest_congregant",
            ),
            models.CheckConstraint(
                check=~Q(member__isnull=False, guest_profile__isnull=False),
                name="organizations_church_congregant_single_account_identity",
            ),
            models.CheckConstraint(
                check=~Q(display_name_snapshot=""),
                name="organizations_church_congregant_display_name_required",
            ),
            models.CheckConstraint(
                check=(
                    Q(directory_visibility=ChurchDirectoryVisibility.STAFF_ONLY)
                    | Q(directory_consent_at__isnull=False)
                ),
                name="organizations_church_congregant_directory_consent_required",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status", "is_active"]),
            models.Index(fields=["workspace", "campus", "status"]),
            models.Index(fields=["workspace", "directory_visibility", "is_active"]),
        ]

    def clean(self):
        super().clean()

        if self.member_id and self.guest_profile_id:
            raise ValidationError("A congregant cannot be both Member-backed and Guest-backed.")

        if not (self.display_name_snapshot or "").strip():
            raise ValidationError({"display_name_snapshot": "A display name snapshot is required."})

        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({"campus": "Congregant campus must belong to the same Church workspace."})

        if self.official_membership_id:
            membership = self.official_membership
            if not self.member_id:
                raise ValidationError({"official_membership": "Official membership requires a Member-backed congregant."})
            if membership.member_id != self.member_id:
                raise ValidationError({"official_membership": "Official membership must belong to the same Member."})
            if membership.organization_id != self.workspace.activation.organization_id:
                raise ValidationError({"official_membership": "Official membership must belong to the same Organization."})

        if self.directory_visibility == ChurchDirectoryVisibility.ORGANIZATION_MEMBERS:
            if not self.member_id:
                raise ValidationError({"directory_visibility": "Only Member-backed congregants can join the member directory."})
            if not self.official_membership_id:
                raise ValidationError({"official_membership": "Organization member-directory visibility requires an active official Organization membership."})
            if self.official_membership.status not in ACCESS_ELIGIBLE_MEMBERSHIP_STATUSES:
                raise ValidationError({"official_membership": "Organization member-directory visibility requires an active official Organization membership."})
            if not self.directory_consent_at:
                raise ValidationError({"directory_consent_at": "Member directory visibility requires explicit consent."})

    @property
    def is_current_official_member(self) -> bool:
        membership = self.official_membership
        return bool(membership and membership.is_current)

    def __str__(self):
        return f"{self.workspace_id}:{self.display_name_snapshot}"


class ChurchHousehold(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    workspace = models.ForeignKey(
        "organizations.ChurchWorkspace",
        on_delete=models.CASCADE,
        related_name="households",
    )
    name = models.CharField(max_length=160)
    campus = models.ForeignKey(
        "organizations.ChurchCampus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="church_households",
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchHouseholdStatus.choices,
        default=ChurchHouseholdStatus.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_church_households",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Household"
        verbose_name_plural = "Church Households"
        ordering = ("name", "id")
        indexes = [
            models.Index(fields=["workspace", "status", "name"]),
            models.Index(fields=["workspace", "campus", "status"]),
        ]

    def clean(self):
        super().clean()
        if self.campus_id and self.campus.workspace_id != self.workspace_id:
            raise ValidationError({"campus": "Household campus must belong to the same Church workspace."})
        if not (self.name or "").strip():
            raise ValidationError({"name": "Household name is required."})

    def __str__(self):
        return f"{self.workspace_id}:{self.name}"


class ChurchHouseholdMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    household = models.ForeignKey(
        ChurchHousehold,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    congregant = models.ForeignKey(
        ChurchCongregant,
        on_delete=models.CASCADE,
        related_name="household_memberships",
    )
    relationship_type = models.CharField(
        max_length=20,
        choices=ChurchHouseholdRelationship.choices,
        default=ChurchHouseholdRelationship.OTHER,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ChurchHouseholdMembershipStatus.choices,
        default=ChurchHouseholdMembershipStatus.ACTIVE,
        db_index=True,
    )

    # MySQL-safe slots.
    active_slot = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    primary_slot = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    is_primary = models.BooleanField(default=False, db_index=True)

    joined_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Church Household Membership"
        verbose_name_plural = "Church Household Memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["congregant", "active_slot"],
                name="organizations_church_unique_active_household_membership",
            ),
            models.UniqueConstraint(
                fields=["household", "primary_slot"],
                name="organizations_church_unique_primary_household_member",
            ),
            models.CheckConstraint(
                check=(
                    Q(status=ChurchHouseholdMembershipStatus.ACTIVE, ended_at__isnull=True)
                    | Q(status=ChurchHouseholdMembershipStatus.ENDED, ended_at__isnull=False)
                ),
                name="organizations_church_household_member_state_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["household", "status", "relationship_type"]),
            models.Index(fields=["congregant", "status"]),
        ]

    def _sync_slots(self):
        active = self.status == ChurchHouseholdMembershipStatus.ACTIVE
        self.active_slot = 1 if active else None
        self.primary_slot = 1 if active and self.is_primary else None

    def clean(self):
        super().clean()
        self._sync_slots()

        if self.congregant.workspace_id != self.household.workspace_id:
            raise ValidationError({"congregant": "Household member must belong to the same Church workspace."})

        if self.status == ChurchHouseholdMembershipStatus.ACTIVE and self.ended_at:
            raise ValidationError({"ended_at": "Active household membership cannot have an end timestamp."})
        if self.status == ChurchHouseholdMembershipStatus.ENDED and not self.ended_at:
            raise ValidationError({"ended_at": "Ended household membership requires an end timestamp."})

    def save(self, *args, **kwargs):
        self._sync_slots()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update({"active_slot", "primary_slot"})
            kwargs["update_fields"] = list(update_fields)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.household_id}:{self.congregant_id}:{self.status}"
