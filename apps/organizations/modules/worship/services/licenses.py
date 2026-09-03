# apps/organizations/modules/worship/services/licenses.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.modules.worship.constants import OrganizationMusicLicenseStatus, WorshipAuditEvent, WorshipPermissionKey
from apps.organizations.modules.worship.models import OrganizationMusicLicense, OrganizationMusicLicenseEvidence
from .access import ensure_worship_permission
from .audit import record_worship_audit


def _assert_party(workspace, party, field):
    if party is None:
        return
    if party.workspace_id != workspace.id or not party.is_active:
        raise ValidationError({field: "Rights party must be active and belong to the same Worship workspace."})


def _assert_license_policy(license):
    required = {
        "ugc_use_allowed": license.ugc_use_allowed,
        "streaming_allowed": license.streaming_allowed,
        "synchronization_allowed": license.synchronization_allowed,
        "clipping_allowed": license.clipping_allowed,
        "hosting_allowed": license.hosting_allowed,
        "sublicensing_to_end_users_allowed": license.sublicensing_to_end_users_allowed,
        "perpetual_existing_content_allowed": license.perpetual_existing_content_allowed,
    }
    missing = [key for key, allowed in required.items() if not allowed]
    if missing:
        raise ValidationError({"rights": [f"Required Organization contribution right is missing: {key}." for key in missing]})
    if license.attribution_required and not str(license.attribution_text or "").strip():
        raise ValidationError({"attribution_text": "Attribution text is required by this license."})
    if not license.evidence_items.exists():
        raise ValidationError("At least one private license evidence item is required before activation.")


@transaction.atomic
def create_organization_music_license(*, workspace, actor, licensor, title, master_owner=None, composition_owner=None, **fields):
    ensure_worship_permission(actor=actor, workspace=workspace, permission_key=WorshipPermissionKey.MANAGE_LICENSES)
    _assert_party(workspace, licensor, "licensor")
    _assert_party(workspace, master_owner, "master_owner")
    _assert_party(workspace, composition_owner, "composition_owner")
    title = str(title or "").strip()
    if not title:
        raise ValidationError({"title": "License title is required."})
    license = OrganizationMusicLicense.objects.create(workspace=workspace, licensor=licensor, master_owner=master_owner, composition_owner=composition_owner, title=title, created_by=actor, **fields)
    record_worship_audit(workspace=workspace, event=WorshipAuditEvent.LICENSE_CREATED, actor=actor, entity=license, metadata={"license_type": license.license_type, "reference": license.reference})
    return license


def _hash_uploaded_file(file_obj):
    hasher = hashlib.sha256()
    position = file_obj.tell() if hasattr(file_obj, "tell") else None
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    for chunk in file_obj.chunks() if hasattr(file_obj, "chunks") else iter(lambda: file_obj.read(1024 * 1024), b""):
        hasher.update(chunk)
    if position is not None and hasattr(file_obj, "seek"):
        file_obj.seek(position)
    return hasher.hexdigest()


@transaction.atomic
def add_organization_music_license_evidence(*, license, actor, evidence_type, title, evidence_file, captured_at=None, notes=""):
    locked = OrganizationMusicLicense.objects.select_for_update().select_related("workspace").get(pk=license.pk)
    ensure_worship_permission(actor=actor, workspace=locked.workspace, permission_key=WorshipPermissionKey.MANAGE_LICENSES)
    if locked.status != OrganizationMusicLicenseStatus.DRAFT:
        raise ValidationError("Evidence can be added only while the Organization music license is draft.")
    evidence = OrganizationMusicLicenseEvidence.objects.create(license=locked, evidence_type=evidence_type, title=str(title or "").strip(), evidence_file=evidence_file, sha256=_hash_uploaded_file(evidence_file), captured_at=captured_at, notes=notes or "", created_by=actor)
    record_worship_audit(workspace=locked.workspace, event=WorshipAuditEvent.LICENSE_EVIDENCE_ADDED, actor=actor, entity=locked, metadata={"evidence_public_id": str(evidence.public_id), "evidence_type": evidence.evidence_type, "sha256": evidence.sha256})
    return evidence


@transaction.atomic
def activate_organization_music_license(*, license, actor, now=None):
    now = now or timezone.now()
    locked = OrganizationMusicLicense.objects.select_for_update().select_related("workspace", "licensor", "master_owner", "composition_owner").get(pk=license.pk)
    ensure_worship_permission(actor=actor, workspace=locked.workspace, permission_key=WorshipPermissionKey.MANAGE_LICENSES)
    if locked.status != OrganizationMusicLicenseStatus.DRAFT:
        raise ValidationError("Only draft Organization music licenses can be activated.")
    for name in ("licensor", "master_owner", "composition_owner"):
        _assert_party(locked.workspace, getattr(locked, name), name)
    if locked.effective_from and locked.effective_from > now:
        raise ValidationError("Organization music license is not active yet.")
    if locked.effective_until and locked.effective_until <= now:
        raise ValidationError("Organization music license has already expired.")
    _assert_license_policy(locked)
    locked.status = OrganizationMusicLicenseStatus.ACTIVE
    locked.activated_at = now
    locked.activated_by = actor
    locked.save(update_fields=["status", "activated_at", "activated_by", "updated_at"])
    record_worship_audit(workspace=locked.workspace, event=WorshipAuditEvent.LICENSE_ACTIVATED, actor=actor, entity=locked, metadata={"license_version": locked.license_version, "effective_until": locked.effective_until.isoformat() if locked.effective_until else None})
    return locked


@transaction.atomic
def revoke_organization_music_license(*, license, actor, reason="", now=None):
    now = now or timezone.now()
    locked = OrganizationMusicLicense.objects.select_for_update().select_related("workspace").get(pk=license.pk)
    ensure_worship_permission(actor=actor, workspace=locked.workspace, permission_key=WorshipPermissionKey.MANAGE_LICENSES)
    if locked.status == OrganizationMusicLicenseStatus.REVOKED:
        return locked
    if locked.status != OrganizationMusicLicenseStatus.ACTIVE:
        raise ValidationError("Only an active Organization music license can be revoked.")
    locked.status = OrganizationMusicLicenseStatus.REVOKED
    locked.revoked_at, locked.revoked_by, locked.revoke_reason = now, actor, str(reason or "")[:240]
    locked.save(update_fields=["status", "revoked_at", "revoked_by", "revoke_reason", "updated_at"])
    from .contributions import _revoke_contribution_locked
    for contribution in locked.contributions.select_for_update().filter(status="published").select_related("rights_record", "track"):
        _revoke_contribution_locked(contribution=contribution, actor=actor, reason=(reason or "Organization music license revoked."), now=now)
    record_worship_audit(workspace=locked.workspace, event=WorshipAuditEvent.LICENSE_REVOKED, actor=actor, entity=locked, metadata={"reason": locked.revoke_reason})
    return locked
