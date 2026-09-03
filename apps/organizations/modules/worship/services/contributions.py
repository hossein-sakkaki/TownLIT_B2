# apps/organizations/modules/worship/services/contributions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models import AudioContributor, MusicRightsRecord, MusicTrack, TrackContributor
from apps.audio_catalog.services.publishing import publish_track
from apps.organizations.constants import OrganizationStatus
from apps.organizations.modules.worship.constants import OrganizationMusicContributionStatus, OrganizationMusicLicenseStatus, WorshipAuditEvent, WorshipPermissionKey
from apps.organizations.modules.worship.models import OrganizationMusicContribution
from .access import ensure_worship_permission
from .audit import record_worship_audit
from .licenses import _assert_license_policy


def _license_snapshot(license):
    def pid(link):
        return str(link.rights_party.public_id) if link else None
    return {
        "license_public_id": str(license.public_id), "license_type": license.license_type,
        "license_version": license.license_version, "reference": license.reference,
        "licensor_rights_party_public_id": pid(license.licensor),
        "master_owner_rights_party_public_id": pid(license.master_owner),
        "composition_owner_rights_party_public_id": pid(license.composition_owner),
        "ugc_use_allowed": license.ugc_use_allowed, "streaming_allowed": license.streaming_allowed,
        "synchronization_allowed": license.synchronization_allowed, "adaptation_allowed": license.adaptation_allowed,
        "clipping_allowed": license.clipping_allowed, "hosting_allowed": license.hosting_allowed,
        "sublicensing_to_end_users_allowed": license.sublicensing_to_end_users_allowed,
        "perpetual_existing_content_allowed": license.perpetual_existing_content_allowed,
        "attribution_required": license.attribution_required, "attribution_text": license.attribution_text,
        "territory_mode": license.territory_mode, "territory_codes": list(license.territory_codes or []),
        "effective_from": license.effective_from.isoformat() if license.effective_from else None,
        "effective_until": license.effective_until.isoformat() if license.effective_until else None,
        "restrictions": deepcopy(license.restrictions or {}),
    }


def _validate_current_license(license, now):
    if license.status != OrganizationMusicLicenseStatus.ACTIVE:
        raise ValidationError("Organization music license is not active.")
    if license.effective_from and license.effective_from > now:
        raise ValidationError("Organization music license is not active yet.")
    if license.effective_until and license.effective_until <= now:
        raise ValidationError("Organization music license has expired.")
    _assert_license_policy(license)


@transaction.atomic
def create_organization_music_contribution(*, workspace, license, actor, catalog, primary_artist: AudioContributor, title, subtitle="", description="", duration_ms=1, language_code="", is_instrumental=True, has_vocals=False, is_explicit=False, is_ai_assisted=False, credit_text="", metadata=None):
    ensure_worship_permission(actor=actor, workspace=workspace, permission_key=WorshipPermissionKey.MANAGE_CONTRIBUTIONS)
    if license.workspace_id != workspace.id:
        raise ValidationError({"license": "Music license must belong to the same Worship workspace."})
    if not getattr(catalog, "is_active", False):
        raise ValidationError({"catalog": "Audio Catalog must be active."})
    if not getattr(primary_artist, "is_active", False):
        raise ValidationError({"primary_artist": "Primary artist must be active."})
    title = str(title or "").strip()
    if not title:
        raise ValidationError({"title": "Track title is required."})
    credit = str(credit_text or primary_artist.display_name or "").strip()
    if not credit:
        raise ValidationError({"credit_text": "Primary artist credit is required."})
    track = MusicTrack.objects.create(
        catalog=catalog, title=title, subtitle=str(subtitle or "").strip(), description=description or "",
        source_type=MusicTrack.SourceType.ARTIST_LICENSED, status=MusicTrack.Status.DRAFT,
        duration_ms=duration_ms, language_code=language_code or "", is_instrumental=is_instrumental,
        has_vocals=has_vocals, is_explicit=is_explicit, is_ai_assisted=is_ai_assisted,
        allow_ugc=True, allow_streaming=True, allow_standalone_download=False,
        allow_external_export=False, allow_commercial_accounts=False,
        created_by=actor, updated_by=actor,
        metadata={**(metadata or {}), "organization_music_contribution": True},
    )
    TrackContributor.objects.create(track=track, contributor=primary_artist, role=TrackContributor.Role.PRIMARY_ARTIST, credit_text=credit, share_basis_points=10000, sort_order=0)
    contribution = OrganizationMusicContribution.objects.create(workspace=workspace, license=license, track=track, primary_artist=primary_artist, credit_text=credit, created_by=actor, metadata=metadata or {})
    record_worship_audit(workspace=workspace, event=WorshipAuditEvent.CONTRIBUTION_CREATED, actor=actor, entity=contribution, metadata={"track_public_id": str(track.public_id), "license_public_id": str(license.public_id), "artist_public_id": str(primary_artist.public_id)})
    return contribution


@transaction.atomic
def publish_organization_music_contribution(*, contribution, actor, now=None):
    now = now or timezone.now()
    locked = OrganizationMusicContribution.objects.select_for_update().select_related("workspace__activation__organization", "license__licensor__rights_party", "license__master_owner__rights_party", "license__composition_owner__rights_party", "track", "primary_artist").get(pk=contribution.pk)
    ensure_worship_permission(actor=actor, workspace=locked.workspace, permission_key=WorshipPermissionKey.PUBLISH_CONTRIBUTIONS)
    if locked.status != OrganizationMusicContributionStatus.DRAFT:
        raise ValidationError("Only draft Organization music contributions can be published.")
    current_license = locked.license.__class__.objects.select_for_update().select_related("licensor__rights_party", "master_owner__rights_party", "composition_owner__rights_party").get(pk=locked.license_id)
    _validate_current_license(current_license, now)
    if locked.workspace.activation.organization.status != OrganizationStatus.ACTIVE:
        raise ValidationError("Organization must be active to publish music contributions.")
    if not locked.track.contributor_links.filter(contributor=locked.primary_artist, role=TrackContributor.Role.PRIMARY_ARTIST).exists():
        raise ValidationError("Organization music contribution requires its primary artist credit link.")
    origin = {
        "type": "organization_contribution",
        "organization_public_id": str(locked.workspace.activation.organization.public_id),
        "workspace_public_id": str(locked.workspace.public_id),
        "license_public_id": str(current_license.public_id),
        "license_version": current_license.license_version,
        "contribution_public_id": str(locked.public_id),
    }
    restrictions = deepcopy(current_license.restrictions or {})
    restrictions["townlit_origin"] = origin
    restrictions["platform_scope"] = {
        "townlit_content_creation_only": True,
        "standalone_download": False,
        "external_export": False,
        "arbitrary_commercial_reuse": False,
    }
    rights, _ = MusicRightsRecord.objects.update_or_create(
        track=locked.track,
        defaults={
            "status": MusicRightsRecord.Status.CLEARED,
            "license_type": current_license.license_type,
            "master_owner": current_license.master_owner.rights_party if current_license.master_owner else None,
            "composition_owner": current_license.composition_owner.rights_party if current_license.composition_owner else None,
            "licensor": current_license.licensor.rights_party,
            "provider_name": locked.workspace.activation.organization.name,
            "provider_plan": "TownLIT Organization Music Contribution",
            "agreement_reference": current_license.reference,
            "license_version": current_license.license_version,
            "effective_from": current_license.effective_from,
            "effective_until": current_license.effective_until,
            "territory_mode": current_license.territory_mode,
            "territory_codes": list(current_license.territory_codes or []),
            "commercial_use_allowed": current_license.commercial_use_allowed,
            "ugc_use_allowed": True,
            "streaming_allowed": True,
            "synchronization_allowed": True,
            "adaptation_allowed": current_license.adaptation_allowed,
            "clipping_allowed": True,
            "hosting_allowed": True,
            "sublicensing_to_end_users_allowed": True,
            "standalone_download_allowed": False,
            "external_export_allowed": False,
            "perpetual_existing_content_allowed": True,
            "attribution_required": current_license.attribution_required,
            "attribution_text": current_license.attribution_text,
            "restrictions": restrictions,
            "reviewed_by": actor,
            "reviewed_at": now,
        },
    )
    track = locked.track
    track.source_type = MusicTrack.SourceType.ARTIST_LICENSED
    track.allow_ugc, track.allow_streaming = True, True
    track.allow_standalone_download, track.allow_external_export, track.allow_commercial_accounts = False, False, False
    track.updated_by = actor
    track.save(update_fields=["source_type", "allow_ugc", "allow_streaming", "allow_standalone_download", "allow_external_export", "allow_commercial_accounts", "updated_by", "updated_at"])
    locked.status = OrganizationMusicContributionStatus.PUBLISHED
    locked.published_at, locked.published_by = now, actor
    locked.rights_record = rights
    locked.license_snapshot = _license_snapshot(current_license)
    locked.save(update_fields=["status", "published_at", "published_by", "rights_record", "license_snapshot", "updated_at"])
    publish_track(track, actor=actor)
    record_worship_audit(workspace=locked.workspace, event=WorshipAuditEvent.CONTRIBUTION_PUBLISHED, actor=actor, entity=locked, metadata={"track_public_id": str(track.public_id), "rights_public_id": str(rights.public_id), "license_public_id": str(current_license.public_id)})
    return locked


def _revoke_contribution_locked(*, contribution, actor, reason, now):
    if contribution.status != OrganizationMusicContributionStatus.PUBLISHED:
        return contribution
    contribution.status = OrganizationMusicContributionStatus.REVOKED
    contribution.revoked_at, contribution.revoked_by, contribution.revoke_reason = now, actor, str(reason or "")[:240]
    contribution.save(update_fields=["status", "revoked_at", "revoked_by", "revoke_reason", "updated_at"])
    rights = contribution.rights_record
    if rights and rights.status != MusicRightsRecord.Status.REVOKED:
        rights.status = MusicRightsRecord.Status.REVOKED
        rights.reviewed_by, rights.reviewed_at = actor, now
        rights.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    # Track, variants, artworks, and existing usage grants intentionally remain intact.
    record_worship_audit(workspace=contribution.workspace, event=WorshipAuditEvent.CONTRIBUTION_REVOKED, actor=actor, entity=contribution, metadata={"track_public_id": str(contribution.track.public_id), "reason": contribution.revoke_reason, "prospective_only": True})
    return contribution


@transaction.atomic
def revoke_organization_music_contribution(*, contribution, actor, reason="", now=None):
    now = now or timezone.now()
    locked = OrganizationMusicContribution.objects.select_for_update().select_related("workspace", "rights_record", "track").get(pk=contribution.pk)
    ensure_worship_permission(actor=actor, workspace=locked.workspace, permission_key=WorshipPermissionKey.PUBLISH_CONTRIBUTIONS)
    return _revoke_contribution_locked(contribution=locked, actor=actor, reason=reason or "Organization music contribution revoked.", now=now)
