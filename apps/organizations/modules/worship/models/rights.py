# apps/organizations/modules/worship/models/rights.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from utils.common.utils import FileUpload
from validators.security_validators import validate_no_executable_file

from apps.organizations.modules.worship.constants import (
    OrganizationMusicContributionStatus,
    OrganizationMusicLicenseStatus,
    WorshipRightsPartyRelationship,
)


LICENSE_EVIDENCE = FileUpload("organizations", "worship", "music_licenses")


class OrganizationRightsParty(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    workspace = models.ForeignKey("organizations.WorshipWorkspace", on_delete=models.CASCADE, related_name="rights_parties")
    rights_party = models.ForeignKey("audio_catalog.RightsParty", on_delete=models.PROTECT, related_name="organization_links")
    relationship = models.CharField(max_length=24, choices=WorshipRightsPartyRelationship.choices, default=WorshipRightsPartyRelationship.OTHER, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("rights_party__display_name", "id")
        constraints = [models.UniqueConstraint(fields=("workspace", "rights_party"), name="organizations_worship_unique_rights_party")]
        indexes = [models.Index(fields=("workspace", "is_active", "relationship"))]

    def __str__(self):
        return f"{self.workspace_id}:{self.rights_party.display_name}"


class OrganizationMusicLicense(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    workspace = models.ForeignKey("organizations.WorshipWorkspace", on_delete=models.CASCADE, related_name="music_licenses")
    licensor = models.ForeignKey(OrganizationRightsParty, on_delete=models.PROTECT, related_name="licenses_as_licensor")
    master_owner = models.ForeignKey(OrganizationRightsParty, null=True, blank=True, on_delete=models.PROTECT, related_name="licenses_as_master_owner")
    composition_owner = models.ForeignKey(OrganizationRightsParty, null=True, blank=True, on_delete=models.PROTECT, related_name="licenses_as_composition_owner")
    status = models.CharField(max_length=16, choices=OrganizationMusicLicenseStatus.choices, default=OrganizationMusicLicenseStatus.DRAFT, db_index=True)
    title = models.CharField(max_length=180)
    reference = models.CharField(max_length=220, blank=True, default="", db_index=True)
    license_type = models.CharField(max_length=24, choices=(
        ("owned", "Owned"), ("assignment", "Assigned"), ("exclusive", "Exclusive License"),
        ("non_exclusive", "Non-exclusive License"), ("public_domain", "Public Domain"),
        ("provider_terms", "Provider Terms"), ("other", "Other"),
    ), default="non_exclusive", db_index=True)
    license_version = models.CharField(max_length=100, blank=True, default="")
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_until = models.DateTimeField(null=True, blank=True)
    territory_mode = models.CharField(max_length=20, choices=(("worldwide", "Worldwide"), ("allow_list", "Allow List"), ("deny_list", "Deny List")), default="worldwide", db_index=True)
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
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="activated_organization_music_licenses")
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="revoked_organization_music_licenses")
    revoke_reason = models.CharField(max_length=240, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_organization_music_licenses")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("workspace", "status", "effective_until")), models.Index(fields=("status", "effective_from", "effective_until"))]
        constraints = [
            models.CheckConstraint(check=Q(effective_until__isnull=True) | Q(effective_from__isnull=True) | Q(effective_until__gt=models.F("effective_from")), name="organizations_worship_license_range_valid"),
        ]

    def __str__(self):
        return self.title


class OrganizationMusicLicenseEvidence(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    license = models.ForeignKey(OrganizationMusicLicense, on_delete=models.CASCADE, related_name="evidence_items")
    evidence_type = models.CharField(max_length=32, choices=(("agreement", "Agreement"), ("assignment", "Assignment"), ("consent", "Consent"), ("invoice", "Invoice"), ("terms", "Terms"), ("source_capture", "Source Capture"), ("other", "Other")), db_index=True)
    title = models.CharField(max_length=180)
    evidence_file = models.FileField(upload_to=LICENSE_EVIDENCE.dir_upload, max_length=700, validators=[validate_no_executable_file])
    sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="organization_music_license_evidence")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("evidence_type", "created_at", "id")
        indexes = [models.Index(fields=("license", "evidence_type")), models.Index(fields=("sha256",))]

    def __str__(self):
        return self.title


class OrganizationMusicContribution(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    workspace = models.ForeignKey("organizations.WorshipWorkspace", on_delete=models.CASCADE, related_name="music_contributions")
    license = models.ForeignKey(OrganizationMusicLicense, on_delete=models.PROTECT, related_name="contributions")
    track = models.OneToOneField("audio_catalog.MusicTrack", on_delete=models.PROTECT, related_name="organization_music_contribution")
    primary_artist = models.ForeignKey("audio_catalog.AudioContributor", on_delete=models.PROTECT, related_name="organization_music_contributions")
    rights_record = models.OneToOneField("audio_catalog.MusicRightsRecord", null=True, blank=True, on_delete=models.PROTECT, related_name="organization_contribution")
    status = models.CharField(max_length=16, choices=OrganizationMusicContributionStatus.choices, default=OrganizationMusicContributionStatus.DRAFT, db_index=True)
    credit_text = models.CharField(max_length=240)
    license_snapshot = models.JSONField(default=dict, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="published_organization_music_contributions")
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="revoked_organization_music_contributions")
    revoke_reason = models.CharField(max_length=240, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_organization_music_contributions")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("workspace", "status", "created_at")), models.Index(fields=("license", "status", "created_at"))]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(status="draft", published_at__isnull=True, revoked_at__isnull=True)
                    | Q(status="published", published_at__isnull=False, revoked_at__isnull=True)
                    | Q(status="revoked", published_at__isnull=False, revoked_at__isnull=False)
                ),
                name="organizations_worship_contribution_lifecycle",
            ),
        ]

    def __str__(self):
        return f"{self.track.title} · {self.status}"
