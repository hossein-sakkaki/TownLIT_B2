# apps/organizations/modules/worship/models/rights.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from utils.common.utils import FileUpload
from validators.security_validators import validate_no_executable_file

from apps.organizations.modules.worship.constants import (
    OrganizationMusicContributionStatus,
    OrganizationMusicLicenseStatus,
    WorshipRightsPartyRelationship,
)


LICENSE_EVIDENCE = FileUpload(
    "organizations",
    "worship",
    "music_licenses",
)

def organization_music_license_evidence_upload_to(
    instance,
    filename,
):
    return LICENSE_EVIDENCE.dir_upload(
        instance,
        filename,
    )

class OrganizationRightsParty(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    workspace = models.ForeignKey(
        "organizations.WorshipWorkspace",
        on_delete=models.CASCADE,
        related_name="rights_parties",
    )
    rights_party = models.ForeignKey(
        "audio_catalog.RightsParty",
        on_delete=models.PROTECT,
        related_name="organization_links",
    )

    relationship = models.CharField(
        max_length=24,
        choices=WorshipRightsPartyRelationship.choices,
        default=WorshipRightsPartyRelationship.OTHER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("rights_party__display_name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "rights_party"),
                name="organizations_worship_unique_rights_party",
            ),
        ]
        indexes = [
            models.Index(fields=("workspace", "is_active", "relationship")),
        ]

    def __str__(self):
        return f"{self.workspace_id}:{self.rights_party.display_name}"


class OrganizationMusicLicense(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    workspace = models.ForeignKey(
        "organizations.WorshipWorkspace",
        on_delete=models.CASCADE,
        related_name="music_licenses",
    )
    licensor = models.ForeignKey(
        OrganizationRightsParty,
        on_delete=models.PROTECT,
        related_name="licenses_as_licensor",
    )
    master_owner = models.ForeignKey(
        OrganizationRightsParty,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="licenses_as_master_owner",
    )
    composition_owner = models.ForeignKey(
        OrganizationRightsParty,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="licenses_as_composition_owner",
    )

    status = models.CharField(
        max_length=16,
        choices=OrganizationMusicLicenseStatus.choices,
        default=OrganizationMusicLicenseStatus.DRAFT,
        db_index=True,
    )

    title = models.CharField(max_length=180)
    reference = models.CharField(max_length=220, blank=True, default="", db_index=True)

    license_type = models.CharField(
        max_length=24,
        choices=(
            ("owned", "Owned"),
            ("assignment", "Assigned"),
            ("exclusive", "Exclusive License"),
            ("non_exclusive", "Non-exclusive License"),
            ("public_domain", "Public Domain"),
            ("provider_terms", "Provider Terms"),
            ("other", "Other"),
        ),
        default="non_exclusive",
        db_index=True,
    )

    license_version = models.CharField(max_length=100, blank=True, default="")

    effective_from = models.DateTimeField(null=True, blank=True)
    effective_until = models.DateTimeField(null=True, blank=True)

    territory_mode = models.CharField(
        max_length=20,
        choices=(
            ("worldwide", "Worldwide"),
            ("allow_list", "Allow List"),
            ("deny_list", "Deny List"),
        ),
        default="worldwide",
        db_index=True,
    )
    territory_codes = models.JSONField(default=list, blank=True)

    commercial_use_allowed = models.BooleanField(default=False)
    ugc_use_allowed = models.BooleanField(default=False)
    streaming_allowed = models.BooleanField(default=False)
    synchronization_allowed = models.BooleanField(default=False)
    adaptation_allowed = models.BooleanField(default=False)
    clipping_allowed = models.BooleanField(default=False)
    hosting_allowed = models.BooleanField(default=False)
    sublicensing_to_end_users_allowed = models.BooleanField(default=False)
    standalone_download_allowed = models.BooleanField(default=False)
    external_export_allowed = models.BooleanField(default=False)
    perpetual_existing_content_allowed = models.BooleanField(default=False)

    attribution_required = models.BooleanField(default=False)
    attribution_text = models.TextField(blank=True, default="")
    restrictions = models.JSONField(default=dict, blank=True)

    activated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activated_organization_music_licenses",
    )

    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_organization_music_licenses",
    )
    revoke_reason = models.CharField(max_length=240, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_organization_music_licenses",
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    _IMMUTABLE_AFTER_DRAFT_FIELDS = (
        "workspace_id",
        "licensor_id",
        "master_owner_id",
        "composition_owner_id",
        "title",
        "reference",
        "license_type",
        "license_version",
        "effective_from",
        "effective_until",
        "territory_mode",
        "territory_codes",
        "commercial_use_allowed",
        "ugc_use_allowed",
        "streaming_allowed",
        "synchronization_allowed",
        "adaptation_allowed",
        "clipping_allowed",
        "hosting_allowed",
        "sublicensing_to_end_users_allowed",
        "standalone_download_allowed",
        "external_export_allowed",
        "perpetual_existing_content_allowed",
        "attribution_required",
        "attribution_text",
        "restrictions",
        "activated_at",
        "activated_by_id",
        "created_by_id",
        "metadata",
    )

    _ALLOWED_TRANSITIONS = {
        OrganizationMusicLicenseStatus.DRAFT: {
            OrganizationMusicLicenseStatus.DRAFT,
            OrganizationMusicLicenseStatus.ACTIVE,
        },
        OrganizationMusicLicenseStatus.ACTIVE: {
            OrganizationMusicLicenseStatus.ACTIVE,
            OrganizationMusicLicenseStatus.EXPIRED,
            OrganizationMusicLicenseStatus.REVOKED,
        },
        OrganizationMusicLicenseStatus.EXPIRED: {
            OrganizationMusicLicenseStatus.EXPIRED,
        },
        OrganizationMusicLicenseStatus.REVOKED: {
            OrganizationMusicLicenseStatus.REVOKED,
        },
    }

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("workspace", "status", "effective_until")),
            models.Index(fields=("status", "effective_from", "effective_until")),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(effective_until__isnull=True)
                    | Q(effective_from__isnull=True)
                    | Q(effective_until__gt=models.F("effective_from"))
                ),
                name="organizations_worship_license_range_valid",
            ),
        ]

    def _validate_persisted_state(self):
        if not self.pk:
            return

        fields = ["status", *self._IMMUTABLE_AFTER_DRAFT_FIELDS, "revoked_at", "revoked_by_id", "revoke_reason"]
        current = type(self).objects.filter(pk=self.pk).values(*fields).first()

        if not current:
            return

        allowed = self._ALLOWED_TRANSITIONS.get(current["status"], {current["status"]})

        if self.status not in allowed:
            raise ValidationError({
                "status": f"Unsupported Organization music license transition: {current['status']} → {self.status}.",
            })

        if current["status"] == OrganizationMusicLicenseStatus.DRAFT:
            return

        immutable_fields = list(self._IMMUTABLE_AFTER_DRAFT_FIELDS)

        if current["status"] == OrganizationMusicLicenseStatus.REVOKED:
            immutable_fields.extend(("revoked_at", "revoked_by_id", "revoke_reason"))

        changed = [
            field
            for field in immutable_fields
            if getattr(self, field) != current[field]
        ]

        if changed:
            raise ValidationError({
                "license": (
                    "Organization music license terms are immutable after activation. "
                    f"Changed fields: {', '.join(sorted(changed))}."
                ),
            })

    def save(self, *args, **kwargs):
        self._validate_persisted_state()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class OrganizationMusicLicenseEvidence(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    license = models.ForeignKey(
        OrganizationMusicLicense,
        on_delete=models.CASCADE,
        related_name="evidence_items",
    )

    evidence_type = models.CharField(
        max_length=32,
        choices=(
            ("agreement", "Agreement"),
            ("assignment", "Assignment"),
            ("consent", "Consent"),
            ("invoice", "Invoice"),
            ("terms", "Terms"),
            ("source_capture", "Source Capture"),
            ("other", "Other"),
        ),
        db_index=True,
    )

    title = models.CharField(max_length=180)

    evidence_file = models.FileField(
        upload_to=organization_music_license_evidence_upload_to,
        max_length=700,
        validators=[validate_no_executable_file],
    )

    sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="organization_music_license_evidence",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("evidence_type", "created_at", "id")
        indexes = [
            models.Index(fields=("license", "evidence_type")),
            models.Index(fields=("sha256",)),
        ]

    def _validate_immutable(self):
        if not self.pk:
            return

        current = type(self).objects.filter(pk=self.pk).values(
            "license_id",
            "evidence_type",
            "title",
            "evidence_file",
            "sha256",
            "captured_at",
            "notes",
            "created_by_id",
        ).first()

        if not current:
            return

        current_file = current["evidence_file"] or ""
        incoming_file = getattr(self.evidence_file, "name", "") or ""

        changed = (
            self.license_id != current["license_id"]
            or self.evidence_type != current["evidence_type"]
            or self.title != current["title"]
            or incoming_file != current_file
            or self.sha256 != current["sha256"]
            or self.captured_at != current["captured_at"]
            or self.notes != current["notes"]
            or self.created_by_id != current["created_by_id"]
        )

        if changed:
            raise ValidationError(
                "Organization music license evidence is immutable after creation."
            )

    def save(self, *args, **kwargs):
        self._validate_immutable()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class OrganizationMusicContribution(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    workspace = models.ForeignKey(
        "organizations.WorshipWorkspace",
        on_delete=models.CASCADE,
        related_name="music_contributions",
    )

    license = models.ForeignKey(
        OrganizationMusicLicense,
        on_delete=models.PROTECT,
        related_name="contributions",
    )

    track = models.OneToOneField(
        "audio_catalog.MusicTrack",
        on_delete=models.PROTECT,
        related_name="organization_music_contribution",
    )

    primary_artist = models.ForeignKey(
        "audio_catalog.AudioContributor",
        on_delete=models.PROTECT,
        related_name="organization_music_contributions",
    )

    rights_record = models.OneToOneField(
        "audio_catalog.MusicRightsRecord",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="organization_contribution",
    )

    status = models.CharField(
        max_length=16,
        choices=OrganizationMusicContributionStatus.choices,
        default=OrganizationMusicContributionStatus.DRAFT,
        db_index=True,
    )

    credit_text = models.CharField(max_length=240)
    license_snapshot = models.JSONField(default=dict, blank=True)

    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_organization_music_contributions",
    )

    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_organization_music_contributions",
    )
    revoke_reason = models.CharField(max_length=240, blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_organization_music_contributions",
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    _IMMUTABLE_AFTER_PUBLISH_FIELDS = (
        "workspace_id",
        "license_id",
        "track_id",
        "primary_artist_id",
        "rights_record_id",
        "credit_text",
        "license_snapshot",
        "published_at",
        "published_by_id",
        "created_by_id",
        "metadata",
    )

    _ALLOWED_TRANSITIONS = {
        OrganizationMusicContributionStatus.DRAFT: {
            OrganizationMusicContributionStatus.DRAFT,
            OrganizationMusicContributionStatus.PUBLISHED,
        },
        OrganizationMusicContributionStatus.PUBLISHED: {
            OrganizationMusicContributionStatus.PUBLISHED,
            OrganizationMusicContributionStatus.REVOKED,
        },
        OrganizationMusicContributionStatus.REVOKED: {
            OrganizationMusicContributionStatus.REVOKED,
        },
    }

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("workspace", "status", "created_at")),
            models.Index(fields=("license", "status", "created_at")),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(
                        status=OrganizationMusicContributionStatus.DRAFT,
                        published_at__isnull=True,
                        revoked_at__isnull=True,
                    )
                    | Q(
                        status=OrganizationMusicContributionStatus.PUBLISHED,
                        published_at__isnull=False,
                        revoked_at__isnull=True,
                    )
                    | Q(
                        status=OrganizationMusicContributionStatus.REVOKED,
                        published_at__isnull=False,
                        revoked_at__isnull=False,
                    )
                ),
                name="organizations_worship_contribution_lifecycle",
            ),
        ]

    def _validate_persisted_state(self):
        if not self.pk:
            return

        fields = ["status", *self._IMMUTABLE_AFTER_PUBLISH_FIELDS, "revoked_at", "revoked_by_id", "revoke_reason"]
        current = type(self).objects.filter(pk=self.pk).values(*fields).first()

        if not current:
            return

        allowed = self._ALLOWED_TRANSITIONS.get(current["status"], {current["status"]})

        if self.status not in allowed:
            raise ValidationError({
                "status": f"Unsupported Organization music contribution transition: {current['status']} → {self.status}.",
            })

        if current["status"] == OrganizationMusicContributionStatus.DRAFT:
            return

        immutable_fields = list(self._IMMUTABLE_AFTER_PUBLISH_FIELDS)

        if current["status"] == OrganizationMusicContributionStatus.REVOKED:
            immutable_fields.extend(("revoked_at", "revoked_by_id", "revoke_reason"))

        changed = [
            field
            for field in immutable_fields
            if getattr(self, field) != current[field]
        ]

        if changed:
            raise ValidationError({
                "contribution": (
                    "Published Organization music contributions are immutable. "
                    f"Changed fields: {', '.join(sorted(changed))}."
                ),
            })

    def save(self, *args, **kwargs):
        self._validate_persisted_state()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.track.title} · {self.status}"