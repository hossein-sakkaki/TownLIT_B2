# apps/audio_catalog/services/usage.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from apps.audio_catalog.models import AudioUsageGrant
from apps.audio_catalog.services.usage_grants import replace_audio_usage_grant

from .availability import can_use_track


@dataclass(frozen=True)
class UsageSelection:
    track: object
    variant: object
    clip_start_ms: int
    clip_duration_ms: int
    music_volume: float = 1.0
    source_audio_volume: float = 1.0
    fade_in_ms: int = 0
    fade_out_ms: int = 0


def _validate(selection):
    track, variant = selection.track, selection.variant

    if variant.track_id != track.id:
        raise ValueError("Variant does not belong to the track.")
    if not variant.is_active:
        raise ValueError("Variant is not active.")
    if not variant.is_converted:
        raise ValueError("Variant is not ready.")
    if not variant.is_streamable:
        raise ValueError("Variant is not streamable.")
    if selection.clip_start_ms < 0:
        raise ValueError("clip_start_ms cannot be negative.")
    if selection.clip_duration_ms <= 0:
        raise ValueError("clip_duration_ms must be greater than zero.")
    if selection.clip_duration_ms < track.min_clip_duration_ms:
        raise ValueError("Clip is shorter than the minimum.")
    if selection.clip_duration_ms > track.max_clip_duration_ms:
        raise ValueError("Clip exceeds the maximum.")
    if selection.clip_start_ms + selection.clip_duration_ms > variant.duration_ms:
        raise ValueError("Clip exceeds the source duration.")
    if selection.fade_in_ms < 0:
        raise ValueError("fade_in_ms cannot be negative.")
    if selection.fade_out_ms < 0:
        raise ValueError("fade_out_ms cannot be negative.")
    if selection.fade_in_ms > selection.clip_duration_ms:
        raise ValueError("fade_in_ms cannot exceed clip duration.")
    if selection.fade_out_ms > selection.clip_duration_ms:
        raise ValueError("fade_out_ms cannot exceed clip duration.")
    if selection.fade_in_ms + selection.fade_out_ms > selection.clip_duration_ms:
        raise ValueError("Combined fades cannot exceed clip duration.")

    for value, name in (
        (selection.music_volume, "music_volume"),
        (selection.source_audio_volume, "source_audio_volume"),
    ):
        normalized = Decimal(str(value))
        if normalized < Decimal("0") or normalized > Decimal("1"):
            raise ValueError(f"{name} must be between 0 and 1.")


def _organization_origin_snapshot(track, rights):
    try:
        contribution = track.organization_music_contribution
    except ObjectDoesNotExist:
        return None

    if contribution.rights_record_id != rights.id:
        raise ValueError(
            "Organization music contribution rights record does not match the track rights."
        )

    license = contribution.license
    workspace = contribution.workspace
    organization = workspace.activation.organization

    def party_snapshot(link):
        if link is None:
            return None

        party = link.rights_party
        return {
            "organization_rights_party_id": link.id,
            "organization_rights_party_public_id": str(link.public_id),
            "rights_party_id": party.id,
            "rights_party_public_id": str(party.public_id),
            "relationship": link.relationship,
        }

    return {
        "type": "organization_contribution",
        "organization_id": organization.id,
        "organization_public_id": str(organization.public_id),
        "worship_workspace_id": workspace.id,
        "worship_workspace_public_id": str(workspace.public_id),
        "contribution_id": contribution.id,
        "contribution_public_id": str(contribution.public_id),
        "contribution_status": contribution.status,
        "contribution_published_at": (
            contribution.published_at.isoformat()
            if contribution.published_at
            else None
        ),
        "license_id": license.id,
        "license_public_id": str(license.public_id),
        "license_status": license.status,
        "license_type": license.license_type,
        "license_version": license.license_version,
        "license_reference": license.reference,
        "license_activated_at": (
            license.activated_at.isoformat()
            if license.activated_at
            else None
        ),
        "licensor": party_snapshot(license.licensor),
        "master_owner": party_snapshot(license.master_owner),
        "composition_owner": party_snapshot(license.composition_owner),
    }


def rights_snapshot(track):
    rights = track.rights

    snapshot = {
        "snapshot_version": 2,
        "rights_record_id": rights.id,
        "rights_public_id": str(rights.public_id),
        "status": rights.status,
        "license_type": rights.license_type,
        "license_version": rights.license_version,
        "provider_name": rights.provider_name,
        "provider_plan": rights.provider_plan,
        "ugc_use_allowed": rights.ugc_use_allowed,
        "streaming_allowed": rights.streaming_allowed,
        "synchronization_allowed": rights.synchronization_allowed,
        "adaptation_allowed": rights.adaptation_allowed,
        "clipping_allowed": rights.clipping_allowed,
        "hosting_allowed": rights.hosting_allowed,
        "sublicensing_to_end_users_allowed": rights.sublicensing_to_end_users_allowed,
        "standalone_download_allowed": rights.standalone_download_allowed,
        "external_export_allowed": rights.external_export_allowed,
        "commercial_use_allowed": rights.commercial_use_allowed,
        "perpetual_existing_content_allowed": rights.perpetual_existing_content_allowed,
        "attribution_required": rights.attribution_required,
        "attribution_text": rights.attribution_text,
        "territory_mode": rights.territory_mode,
        "territory_codes": list(rights.territory_codes or []),
        "effective_from": rights.effective_from.isoformat() if rights.effective_from else None,
        "effective_until": rights.effective_until.isoformat() if rights.effective_until else None,
        "restrictions": deepcopy(rights.restrictions or {}),
    }

    organization_origin = _organization_origin_snapshot(track, rights)

    if organization_origin is not None:
        snapshot["organization_origin"] = organization_origin

    return snapshot


def technical_snapshot(variant):
    return {
        "variant_id": variant.id,
        "variant_public_id": str(variant.public_id),
        "variant_type": variant.variant_type,
        "label": variant.label,
        "locale": variant.locale,
        "duration_ms": variant.duration_ms,
        "mime_type": variant.mime_type,
        "codec": variant.codec,
        "container": variant.container,
        "bitrate_kbps": variant.bitrate_kbps,
        "sample_rate_hz": variant.sample_rate_hz,
        "channels": variant.channels,
        "checksum_sha256": variant.checksum_sha256,
    }


def _primary_artist_name(track):
    primary = (
        track.contributor_links
        .filter(role="primary_artist")
        .select_related("contributor")
        .order_by("sort_order", "id")
        .first()
    )

    return (
        "TownLIT Original"
        if primary is None
        else primary.contributor.display_name
    )


def _lock_content_object(content_object):
    return (
        content_object.__class__._base_manager
        .select_for_update()
        .get(pk=content_object.pk)
    )


@transaction.atomic
def assign_music_to_content(
    content_object,
    selection,
    granted_to=None,
    country_code="",
):
    if content_object is None or content_object.pk is None:
        raise ValueError(
            "Content object must be saved before assigning music."
        )

    availability = can_use_track(
        selection.track,
        country_code=country_code,
    )

    if not availability.allowed:
        raise ValueError(availability.reason)

    _validate(selection)

    locked_content = _lock_content_object(content_object)
    content_type = ContentType.objects.get_for_model(
        locked_content,
        for_concrete_model=False,
    )

    active = list(
        AudioUsageGrant.objects
        .select_for_update()
        .filter(
            content_type=content_type,
            object_id=locked_content.pk,
            status=AudioUsageGrant.Status.ACTIVE,
        )
        .order_by("id")
    )

    for existing in active:
        replace_audio_usage_grant(
            grant=existing,
            reason="Replaced by a new music selection.",
        )

    track, variant = selection.track, selection.variant

    return AudioUsageGrant.objects.create(
        content_type=content_type,
        object_id=locked_content.pk,
        track=track,
        variant=variant,
        clip_start_ms=selection.clip_start_ms,
        clip_duration_ms=selection.clip_duration_ms,
        music_volume=Decimal(str(selection.music_volume)),
        source_audio_volume=Decimal(str(selection.source_audio_volume)),
        fade_in_ms=selection.fade_in_ms,
        fade_out_ms=selection.fade_out_ms,
        track_version_snapshot=track.version,
        title_snapshot=track.title,
        artist_snapshot=_primary_artist_name(track),
        rights_snapshot=rights_snapshot(track),
        technical_snapshot=technical_snapshot(variant),
        granted_to=granted_to,
    )