# apps/audio_catalog/services/usage.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.audio_catalog.models import (
    AudioUsageGrant,
)
from apps.audio_catalog.services.usage_grants import (
    replace_audio_usage_grant,
)

from .availability import can_use_track


@dataclass(frozen=True)
class UsageSelection:
    """
    Validated music selection for one content object.
    """

    track: object
    variant: object

    clip_start_ms: int
    clip_duration_ms: int

    music_volume: float = 1.0
    source_audio_volume: float = 1.0

    fade_in_ms: int = 0
    fade_out_ms: int = 0


def _validate(
    selection: UsageSelection,
) -> None:
    """
    Validate track, variant, clip, and volume configuration.
    """

    track = selection.track
    variant = selection.variant

    if variant.track_id != track.id:
        raise ValueError(
            "Variant does not belong to the track."
        )

    if not variant.is_active:
        raise ValueError(
            "Variant is not active."
        )

    if not variant.is_converted:
        raise ValueError(
            "Variant is not ready."
        )

    if not variant.is_streamable:
        raise ValueError(
            "Variant is not streamable."
        )

    if selection.clip_start_ms < 0:
        raise ValueError(
            "clip_start_ms cannot be negative."
        )

    if selection.clip_duration_ms <= 0:
        raise ValueError(
            "clip_duration_ms must be greater than zero."
        )

    if (
        selection.clip_duration_ms
        < track.min_clip_duration_ms
    ):
        raise ValueError(
            "Clip is shorter than the minimum."
        )

    if (
        selection.clip_duration_ms
        > track.max_clip_duration_ms
    ):
        raise ValueError(
            "Clip exceeds the maximum."
        )

    clip_end_ms = (
        selection.clip_start_ms
        + selection.clip_duration_ms
    )

    if clip_end_ms > variant.duration_ms:
        raise ValueError(
            "Clip exceeds the source duration."
        )

    if selection.fade_in_ms < 0:
        raise ValueError(
            "fade_in_ms cannot be negative."
        )

    if selection.fade_out_ms < 0:
        raise ValueError(
            "fade_out_ms cannot be negative."
        )

    if (
        selection.fade_in_ms
        > selection.clip_duration_ms
    ):
        raise ValueError(
            "fade_in_ms cannot exceed clip duration."
        )

    if (
        selection.fade_out_ms
        > selection.clip_duration_ms
    ):
        raise ValueError(
            "fade_out_ms cannot exceed clip duration."
        )

    if (
        selection.fade_in_ms
        + selection.fade_out_ms
        > selection.clip_duration_ms
    ):
        raise ValueError(
            "Combined fades cannot exceed clip duration."
        )

    volume_fields = (
        (
            selection.music_volume,
            "music_volume",
        ),
        (
            selection.source_audio_volume,
            "source_audio_volume",
        ),
    )

    for value, name in volume_fields:
        normalized = Decimal(
            str(value)
        )

        if (
            normalized < Decimal("0")
            or normalized > Decimal("1")
        ):
            raise ValueError(
                f"{name} must be between 0 and 1."
            )


def rights_snapshot(
    track,
) -> dict:
    """
    Capture the rights state at grant creation time.
    """

    rights = track.rights

    return {
        "rights_record_id": rights.id,
        "rights_public_id": str(
            rights.public_id
        ),
        "status": rights.status,
        "license_type": rights.license_type,
        "license_version": rights.license_version,
        "provider_name": rights.provider_name,
        "provider_plan": rights.provider_plan,
        "ugc_use_allowed": (
            rights.ugc_use_allowed
        ),
        "streaming_allowed": (
            rights.streaming_allowed
        ),
        "synchronization_allowed": (
            rights.synchronization_allowed
        ),
        "clipping_allowed": (
            rights.clipping_allowed
        ),
        "hosting_allowed": (
            rights.hosting_allowed
        ),
        "sublicensing_to_end_users_allowed": (
            rights.sublicensing_to_end_users_allowed
        ),
        "external_export_allowed": (
            rights.external_export_allowed
        ),
        "perpetual_existing_content_allowed": (
            rights.perpetual_existing_content_allowed
        ),
        "attribution_required": (
            rights.attribution_required
        ),
        "attribution_text": (
            rights.attribution_text
        ),
        "territory_mode": (
            rights.territory_mode
        ),
        "territory_codes": list(
            rights.territory_codes
            or []
        ),
        "effective_from": (
            rights.effective_from.isoformat()
            if rights.effective_from
            else None
        ),
        "effective_until": (
            rights.effective_until.isoformat()
            if rights.effective_until
            else None
        ),
    }


def technical_snapshot(
    variant,
) -> dict:
    """
    Capture immutable technical information.
    """

    return {
        "variant_id": variant.id,
        "variant_public_id": str(
            variant.public_id
        ),
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
        "checksum_sha256": (
            variant.checksum_sha256
        ),
    }


def _primary_artist_name(
    track,
) -> str:
    """
    Resolve the primary artist snapshot.
    """

    primary = (
        track.contributor_links
        .filter(
            role="primary_artist",
        )
        .select_related(
            "contributor",
        )
        .order_by(
            "sort_order",
            "id",
        )
        .first()
    )

    if primary is None:
        return "TownLIT Original"

    return primary.contributor.display_name


def _lock_content_object(
    content_object,
):
    """
    Lock the owning content row.

    This serializes concurrent music assignments for the same
    content object, including on MySQL where conditional unique
    constraints may not be enforced.
    """

    model_class = content_object.__class__

    return (
        model_class._base_manager
        .select_for_update()
        .get(
            pk=content_object.pk,
        )
    )


@transaction.atomic
def assign_music_to_content(
    content_object,
    selection: UsageSelection,
    granted_to=None,
    country_code: str = "",
) -> AudioUsageGrant:
    """
    Assign music to content safely.

    Existing active grants are marked as replaced through normal
    model saves so usage analytics signals are triggered.
    """

    if (
        content_object is None
        or content_object.pk is None
    ):
        raise ValueError(
            "Content object must be saved before assigning music."
        )

    availability = can_use_track(
        selection.track,
        country_code=country_code,
    )

    if not availability.allowed:
        raise ValueError(
            availability.reason
        )

    _validate(
        selection
    )

    # Serialize concurrent assignments for this content object.
    locked_content = _lock_content_object(
        content_object
    )

    content_type = (
        ContentType.objects
        .get_for_model(
            locked_content,
            for_concrete_model=False,
        )
    )

    active_grants = list(
        AudioUsageGrant.objects
        .select_for_update()
        .filter(
            content_type=content_type,
            object_id=locked_content.pk,
            status=AudioUsageGrant.Status.ACTIVE,
        )
        .order_by(
            "id",
        )
    )

    for existing_grant in active_grants:
        replace_audio_usage_grant(
            grant=existing_grant,
            reason=(
                "Replaced by a new music selection."
            ),
        )

    track = selection.track
    variant = selection.variant

    grant = AudioUsageGrant.objects.create(
        content_type=content_type,
        object_id=locked_content.pk,
        track=track,
        variant=variant,
        clip_start_ms=(
            selection.clip_start_ms
        ),
        clip_duration_ms=(
            selection.clip_duration_ms
        ),
        music_volume=Decimal(
            str(
                selection.music_volume
            )
        ),
        source_audio_volume=Decimal(
            str(
                selection.source_audio_volume
            )
        ),
        fade_in_ms=selection.fade_in_ms,
        fade_out_ms=selection.fade_out_ms,
        track_version_snapshot=track.version,
        title_snapshot=track.title,
        artist_snapshot=_primary_artist_name(
            track
        ),
        rights_snapshot=rights_snapshot(
            track
        ),
        technical_snapshot=technical_snapshot(
            variant
        ),
        granted_to=granted_to,
    )

    return grant