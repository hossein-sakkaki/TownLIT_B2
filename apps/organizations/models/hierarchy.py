# apps/organizations/models/hierarchy.py
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
    CURRENT_RELATIONSHIP_STATUSES,
    OrganizationRelationshipConsentStatus,
    OrganizationRelationshipStatus,
    OrganizationRelationshipType,
)


EXCLUSIVE_AUTHORITY_RELATIONSHIP_TYPES = (
    OrganizationRelationshipType.PARENT_BRANCH,
    OrganizationRelationshipType.SPONSORSHIP,
)


class OrganizationRelationship(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # Source is the parent, authority, network, or sponsor.
    source_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="outgoing_relationships",
    )
    target_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="incoming_relationships",
    )
    relationship_type = models.CharField(
        max_length=30,
        choices=OrganizationRelationshipType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationRelationshipStatus.choices,
        default=OrganizationRelationshipStatus.PENDING,
        db_index=True,
    )

    # MySQL-safe uniqueness for the current relationship.
    current_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    # Limits exclusive authority types to one current authority.
    authority_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    requested_by_organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_relationships",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_organization_relationships",
    )

    activated_at = models.DateTimeField(
        null=True,
        blank=True,
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
        max_length=1000,
        null=True,
        blank=True,
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Relationship"
        verbose_name_plural = "Organization Relationships"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                check=~Q(
                    source_organization=models.F(
                        "target_organization"
                    )
                ),
                name="organizations_relationship_distinct_parties",
            ),
            models.UniqueConstraint(
                fields=[
                    "source_organization",
                    "target_organization",
                    "relationship_type",
                    "current_slot",
                ],
                name="organizations_unique_current_relationship",
            ),
            models.UniqueConstraint(
                fields=[
                    "target_organization",
                    "relationship_type",
                    "authority_slot",
                ],
                name="organizations_unique_current_authority",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "source_organization",
                    "relationship_type",
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "target_organization",
                    "relationship_type",
                    "status",
                ]
            ),
        ]

    def _sync_slots(self):
        is_current = self.status in CURRENT_RELATIONSHIP_STATUSES
        self.current_slot = 1 if is_current else None
        self.authority_slot = (
            1
            if is_current
            and self.relationship_type
            in EXCLUSIVE_AUTHORITY_RELATIONSHIP_TYPES
            else None
        )

    def clean(self):
        super().clean()
        self._sync_slots()

        if (
            self.source_organization_id
            and self.source_organization_id
            == self.target_organization_id
        ):
            raise ValidationError(
                "An organization cannot relate to itself."
            )

        if self.requested_by_organization_id not in {
            None,
            self.source_organization_id,
            self.target_organization_id,
        }:
            raise ValidationError({
                "requested_by_organization": (
                    "The requesting organization must be one of "
                    "the relationship parties."
                ),
            })

    def save(self, *args, **kwargs):
        self._sync_slots()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update({"current_slot", "authority_slot"})
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    @property
    def is_current(self) -> bool:
        return self.status in CURRENT_RELATIONSHIP_STATUSES

    def __str__(self):
        return (
            f"{self.source_organization_id}:"
            f"{self.relationship_type}:"
            f"{self.target_organization_id}"
        )


class OrganizationRelationshipConsent(models.Model):
    id = models.BigAutoField(primary_key=True)

    relationship = models.ForeignKey(
        OrganizationRelationship,
        on_delete=models.CASCADE,
        related_name="consents",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="relationship_consents",
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationRelationshipConsentStatus.choices,
        default=OrganizationRelationshipConsentStatus.PENDING,
        db_index=True,
    )

    governance_proposal = models.ForeignKey(
        "organizations.OrganizationGovernanceProposal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relationship_consent_records",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_relationship_consent_decisions",
    )
    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    note = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Relationship Consent"
        verbose_name_plural = "Organization Relationship Consents"
        constraints = [
            models.UniqueConstraint(
                fields=["relationship", "organization"],
                name="organizations_unique_relationship_consent",
            ),
        ]

    def clean(self):
        super().clean()

        if self.organization_id not in {
            self.relationship.source_organization_id,
            self.relationship.target_organization_id,
        }:
            raise ValidationError({
                "organization": (
                    "Consent organization must be a relationship party."
                ),
            })

    def __str__(self):
        return (
            f"{self.relationship_id}:"
            f"{self.organization_id}:"
            f"{self.status}"
        )
