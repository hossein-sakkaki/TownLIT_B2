# apps/audio_catalog/models/rights.py

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from utils.common.utils import FileUpload
from validators.security_validators import (
    validate_no_executable_file,
)

from .base import PublicIDTimestampedModel


# -------------------------------------------------
# Upload roots
# -------------------------------------------------
RIGHTS_EVIDENCE = FileUpload(
    "audio_catalog",
    "documents",
    "rights",
)


class RightsParty(PublicIDTimestampedModel):
    """
    Legal party connected to music rights.
    """

    class Kind(models.TextChoices):
        PERSON = "person", "Person"
        ORGANIZATION = "organization", "Organization"
        LABEL = "label", "Label"
        PUBLISHER = "publisher", "Publisher"
        PRO = "pro", "Performing Rights Organization"
        AI_PROVIDER = "ai_provider", "AI Provider"
        OTHER = "other", "Other"

    display_name = models.CharField(
        max_length=180,
    )

    legal_name = models.CharField(
        max_length=220,
        blank=True,
        default="",
    )

    kind = models.CharField(
        max_length=24,
        choices=Kind.choices,
        db_index=True,
    )

    country_code = models.CharField(
        max_length=2,
        blank=True,
        default="",
    )

    website_url = models.URLField(
        blank=True,
        default="",
    )

    contact_email = models.EmailField(
        blank=True,
        default="",
    )

    external_reference = models.CharField(
        max_length=220,
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = "Rights Party"
        verbose_name_plural = "Rights Parties"

        ordering = [
            "display_name",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "kind",
                    "display_name",
                ]
            ),
            models.Index(
                fields=[
                    "country_code",
                    "kind",
                ]
            ),
        ]

    def __str__(self) -> str:
        return self.display_name


class MusicRightsRecord(PublicIDTimestampedModel):
    """
    Legal and licensing record for one music track.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW_REQUIRED = "review_required", "Review Required"
        CLEARED = "cleared", "Cleared"
        RESTRICTED = "restricted", "Restricted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    class LicenseType(models.TextChoices):
        OWNED = "owned", "Owned"
        ASSIGNMENT = "assignment", "Assigned"
        EXCLUSIVE = "exclusive", "Exclusive License"
        NON_EXCLUSIVE = "non_exclusive", "Non-exclusive License"
        PUBLIC_DOMAIN = "public_domain", "Public Domain"
        PROVIDER_TERMS = "provider_terms", "Provider Terms"
        OTHER = "other", "Other"

    class TerritoryMode(models.TextChoices):
        WORLDWIDE = "worldwide", "Worldwide"
        ALLOW_LIST = "allow_list", "Allow List"
        DENY_LIST = "deny_list", "Deny List"

    # -------------------------------------------------
    # Track
    # -------------------------------------------------
    track = models.OneToOneField(
        "audio_catalog.MusicTrack",
        on_delete=models.CASCADE,
        related_name="rights",
    )

    # -------------------------------------------------
    # Status
    # -------------------------------------------------
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    license_type = models.CharField(
        max_length=24,
        choices=LicenseType.choices,
        default=LicenseType.PROVIDER_TERMS,
        db_index=True,
    )

    # -------------------------------------------------
    # Rights parties
    # -------------------------------------------------
    master_owner = models.ForeignKey(
        RightsParty,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="master_rights",
    )

    composition_owner = models.ForeignKey(
        RightsParty,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="composition_rights",
    )

    licensor = models.ForeignKey(
        RightsParty,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="licenses",
    )

    # -------------------------------------------------
    # Provider and source
    # -------------------------------------------------
    provider_name = models.CharField(
        max_length=140,
        blank=True,
        default="",
    )

    provider_plan = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    provider_account_reference = models.CharField(
        max_length=220,
        blank=True,
        default="",
    )

    generation_reference = models.CharField(
        max_length=500,
        blank=True,
        default="",
    )

    generation_prompt_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
    )

    agreement_reference = models.CharField(
        max_length=220,
        blank=True,
        default="",
    )

    license_version = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    source_url = models.URLField(
        blank=True,
        default="",
    )

    # -------------------------------------------------
    # Validity period
    # -------------------------------------------------
    effective_from = models.DateTimeField(
        null=True,
        blank=True,
    )

    effective_until = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -------------------------------------------------
    # Territory
    # -------------------------------------------------
    territory_mode = models.CharField(
        max_length=20,
        choices=TerritoryMode.choices,
        default=TerritoryMode.WORLDWIDE,
        db_index=True,
    )

    territory_codes = models.JSONField(
        default=list,
        blank=True,
    )

    # -------------------------------------------------
    # Rights matrix
    # -------------------------------------------------
    commercial_use_allowed = models.BooleanField(
        default=False,
    )

    ugc_use_allowed = models.BooleanField(
        default=False,
    )

    streaming_allowed = models.BooleanField(
        default=False,
    )

    synchronization_allowed = models.BooleanField(
        default=False,
    )

    adaptation_allowed = models.BooleanField(
        default=False,
    )

    clipping_allowed = models.BooleanField(
        default=False,
    )

    hosting_allowed = models.BooleanField(
        default=False,
    )

    sublicensing_to_end_users_allowed = models.BooleanField(
        default=False,
    )

    standalone_download_allowed = models.BooleanField(
        default=False,
    )

    external_export_allowed = models.BooleanField(
        default=False,
    )

    perpetual_existing_content_allowed = models.BooleanField(
        default=False,
    )

    attribution_required = models.BooleanField(
        default=False,
    )

    attribution_text = models.TextField(
        blank=True,
        default="",
    )

    restrictions = models.JSONField(
        default=dict,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    # -------------------------------------------------
    # Review
    # -------------------------------------------------
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audio_rights_reviews",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Music Rights Record"
        verbose_name_plural = "Music Rights Records"

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "effective_until",
                ]
            ),
            models.Index(
                fields=[
                    "license_type",
                    "status",
                ]
            ),
            models.Index(
                fields=[
                    "provider_name",
                    "provider_plan",
                ]
            ),
            models.Index(
                fields=[
                    "territory_mode",
                    "status",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=(
                    Q(effective_until__isnull=True)
                    | Q(effective_from__isnull=True)
                    | Q(
                        effective_until__gt=models.F(
                            "effective_from"
                        )
                    )
                ),
                name="audio_rights_effective_range_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"Rights · {self.track.title}"


class RightsEvidence(PublicIDTimestampedModel):
    """
    Private legal evidence for one rights record.
    """

    class EvidenceType(models.TextChoices):
        TERMS = "terms", "Terms"
        INVOICE = "invoice", "Invoice"
        AGREEMENT = "agreement", "Agreement"
        ASSIGNMENT = "assignment", "Assignment"
        CONSENT = "consent", "Consent"
        SOURCE_CAPTURE = "source_capture", "Source Capture"
        GENERATION_RECORD = "generation_record", "Generation Record"
        EDITING_RECORD = "editing_record", "Editing Record"
        OTHER = "other", "Other"

    rights_record = models.ForeignKey(
        MusicRightsRecord,
        on_delete=models.CASCADE,
        related_name="evidence_items",
    )

    evidence_type = models.CharField(
        max_length=32,
        choices=EvidenceType.choices,
        db_index=True,
    )

    title = models.CharField(
        max_length=180,
    )

    evidence_file = models.FileField(
        upload_to=RIGHTS_EVIDENCE.dir_upload,
        max_length=700,
        validators=[
            validate_no_executable_file,
        ],
    )

    sha256 = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    captured_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        verbose_name = "Rights Evidence"
        verbose_name_plural = "Rights Evidence"

        ordering = [
            "evidence_type",
            "created_at",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "rights_record",
                    "evidence_type",
                ]
            ),
            models.Index(
                fields=[
                    "sha256",
                ]
            ),
        ]

    def __str__(self) -> str:
        return self.title