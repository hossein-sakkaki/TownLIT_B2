# apps/organizations/models/verification.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.organizations.upload_paths import organization_verification_upload_to
from apps.organizations.constants import (
    OPEN_VERIFICATION_CASE_STATUSES,
    OrganizationRelationshipType,
    OrganizationVerificationDocumentReviewStatus,
    OrganizationVerificationDocumentType,
    OrganizationVerificationGrantStatus,
    OrganizationVerificationGrantType,
    OrganizationVerificationPath,
    OrganizationVerificationStatus,
)
from common.reference_data.countries import COUNTRY_CHOICES
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.mediaValidators.pdf_validators import validate_pdf_file
from validators.security_validators import validate_no_executable_file


def validate_organization_verification_file(value):
    validate_no_executable_file(value)

    suffix = Path(
        str(getattr(value, "name", "") or "")
    ).suffix.lower()

    if suffix == ".pdf":
        validate_pdf_file(value)
        return

    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        validate_image_file(value)
        validate_image_size(value)
        return

    raise ValidationError(
        "Verification documents must be PDF, JPG, PNG, or WEBP files."
    )


class OrganizationVerificationCase(models.Model):
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
        related_name="verification_cases",
    )
    path = models.CharField(
        max_length=30,
        choices=OrganizationVerificationPath.choices,
        default=OrganizationVerificationPath.DIRECT,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=OrganizationVerificationStatus.choices,
        default=OrganizationVerificationStatus.DRAFT,
        db_index=True,
    )

    # MySQL-safe uniqueness for one open case.
    current_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    renewal_of = models.ForeignKey(
        "organizations.OrganizationVerificationGrant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="renewal_cases",
    )

    relationship = models.ForeignKey(
        "organizations.OrganizationRelationship",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_cases",
    )

    legal_name = models.CharField(
        max_length=240,
        null=True,
        blank=True,
    )
    registration_number = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )
    jurisdiction_country = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        null=True,
        blank=True,
        db_index=True,
    )
    jurisdiction_region = models.CharField(
        max_length=160,
        null=True,
        blank=True,
    )
    registration_authority = models.CharField(
        max_length=240,
        null=True,
        blank=True,
    )
    registered_address = models.TextField(
        null=True,
        blank=True,
    )

    organization_notes = models.TextField(
        null=True,
        blank=True,
    )
    review_notes = models.TextField(
        null=True,
        blank=True,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_organization_verification_cases",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_organization_verification_cases",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    review_started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    decision_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Verification Case"
        verbose_name_plural = "Organization Verification Cases"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "current_slot"],
                name="organizations_unique_open_verification_case",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "status", "created_at"]
            ),
            models.Index(fields=["status", "submitted_at"]),
        ]

    def _sync_current_slot(self):
        self.current_slot = (
            1
            if self.status in OPEN_VERIFICATION_CASE_STATUSES
            else None
        )

    def clean(self):
        super().clean()
        self._sync_current_slot()

        if (
            self.renewal_of_id
            and self.renewal_of.organization_id != self.organization_id
        ):
            raise ValidationError({
                "renewal_of": (
                    "Renewal grant must belong to the same organization."
                ),
            })

        if self.path == OrganizationVerificationPath.DIRECT:
            if self.relationship_id:
                raise ValidationError({
                    "relationship": (
                        "Direct verification cannot reference a sponsor relationship."
                    ),
                })

        if self.path == OrganizationVerificationPath.SPONSORED_BRANCH:
            if not self.relationship_id:
                raise ValidationError({
                    "relationship": (
                        "Sponsored branch verification requires a relationship."
                    ),
                })

            relationship = self.relationship

            if relationship.target_organization_id != self.organization_id:
                raise ValidationError({
                    "relationship": (
                        "The verified organization must be the relationship target."
                    ),
                })

            if relationship.relationship_type not in {
                OrganizationRelationshipType.PARENT_BRANCH,
                OrganizationRelationshipType.SPONSORSHIP,
            }:
                raise ValidationError({
                    "relationship": (
                        "Sponsored verification requires a parent or sponsorship relationship."
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

    def __str__(self):
        return f"{self.organization_id}:{self.path}:{self.status}"


class OrganizationVerificationDocument(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    verification_case = models.ForeignKey(
        OrganizationVerificationCase,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=40,
        choices=OrganizationVerificationDocumentType.choices,
        db_index=True,
    )
    title = models.CharField(
        max_length=240,
        null=True,
        blank=True,
    )
    file = models.FileField(
        upload_to=organization_verification_upload_to,
        validators=[validate_organization_verification_file],
    )
    document_number = models.CharField(
        max_length=160,
        null=True,
        blank=True,
    )
    issued_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)

    review_status = models.CharField(
        max_length=20,
        choices=OrganizationVerificationDocumentReviewStatus.choices,
        default=OrganizationVerificationDocumentReviewStatus.PENDING,
        db_index=True,
    )
    review_note = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_organization_verification_documents",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_organization_verification_documents",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_documents",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Verification Document"
        verbose_name_plural = "Organization Verification Documents"
        ordering = ("created_at",)
        indexes = [
            models.Index(
                fields=[
                    "verification_case",
                    "is_active",
                    "review_status",
                ]
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.issued_at
            and self.expires_at
            and self.expires_at <= self.issued_at
        ):
            raise ValidationError({
                "expires_at": (
                    "Document expiry must be after its issue date."
                ),
            })

    def __str__(self):
        return f"{self.verification_case_id}:{self.document_type}"


class OrganizationVerificationGrant(models.Model):
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
        related_name="verification_grants",
    )
    verification_case = models.ForeignKey(
        OrganizationVerificationCase,
        on_delete=models.PROTECT,
        related_name="grants",
    )
    grant_type = models.CharField(
        max_length=30,
        choices=OrganizationVerificationGrantType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=OrganizationVerificationGrantStatus.choices,
        default=OrganizationVerificationGrantStatus.ACTIVE,
        db_index=True,
    )

    # MySQL-safe uniqueness for one active grant.
    active_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    relationship = models.ForeignKey(
        "organizations.OrganizationRelationship",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verification_grants",
    )
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseded_by_grants",
    )

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_organization_verifications",
    )
    granted_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    revocation_reason = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Verification Grant"
        verbose_name_plural = "Organization Verification Grants"
        ordering = ("-granted_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "active_slot"],
                name="organizations_unique_active_verification_grant",
            ),
            models.CheckConstraint(
                check=(
                    Q(expires_at__isnull=True)
                    | Q(expires_at__gt=models.F("granted_at"))
                ),
                name="organizations_verification_grant_valid_window",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "status", "granted_at"]
            ),
        ]

    def _sync_active_slot(self):
        self.active_slot = (
            1
            if self.status == OrganizationVerificationGrantStatus.ACTIVE
            and self.revoked_at is None
            else None
        )

    def clean(self):
        super().clean()
        self._sync_active_slot()

        if self.verification_case.organization_id != self.organization_id:
            raise ValidationError({
                "verification_case": (
                    "Verification grant and case must belong to the same organization."
                ),
            })

        if self.grant_type == OrganizationVerificationGrantType.DIRECT:
            if self.relationship_id:
                raise ValidationError({
                    "relationship": (
                        "Direct verification grants cannot reference a relationship."
                    ),
                })

        if self.grant_type == OrganizationVerificationGrantType.SPONSORED_BRANCH:
            if not self.relationship_id:
                raise ValidationError({
                    "relationship": (
                        "Sponsored branch grants require a relationship."
                    ),
                })

            if self.relationship.target_organization_id != self.organization_id:
                raise ValidationError({
                    "relationship": (
                        "Sponsored grant relationship must target the verified organization."
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
        return f"{self.organization_id}:{self.grant_type}:{self.status}"
