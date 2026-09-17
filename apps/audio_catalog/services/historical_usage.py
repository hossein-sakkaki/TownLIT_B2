# apps/audio_catalog/services/historical_usage.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from dataclasses import dataclass

from apps.audio_catalog.models import (
    AudioUsageGrant,
    MusicTrack,
)


@dataclass(frozen=True)
class HistoricalAudioUsageAvailability:
    allowed: bool
    reason: str = ""


def can_render_existing_audio_usage(
    grant: AudioUsageGrant,
) -> HistoricalAudioUsageAvailability:
    if grant.status != AudioUsageGrant.Status.ACTIVE:
        return HistoricalAudioUsageAvailability(
            False,
            "Audio usage grant is not active.",
        )

    # Platform suspension is a hard stop.
    if grant.track.status == MusicTrack.Status.SUSPENDED:
        return HistoricalAudioUsageAvailability(
            False,
            "Track is suspended by TownLIT.",
        )

    snapshot = (
        grant.rights_snapshot
        if isinstance(grant.rights_snapshot, dict)
        else {}
    )

    if not snapshot.get(
        "perpetual_existing_content_allowed",
        False,
    ):
        return HistoricalAudioUsageAvailability(
            False,
            "Historical use is not preserved by the grant snapshot.",
        )

    if not grant.variant_id:
        return HistoricalAudioUsageAvailability(
            False,
            "Historical audio grant has no playback variant.",
        )

    variant = grant.variant

    if (
        not variant.audio_file
        or not variant.is_active
        or not variant.is_converted
        or not variant.is_streamable
    ):
        return HistoricalAudioUsageAvailability(
            False,
            "Historical audio variant is unavailable.",
        )

    technical = (
        grant.technical_snapshot
        if isinstance(grant.technical_snapshot, dict)
        else {}
    )

    if int(
        technical.get("variant_id") or 0
    ) != grant.variant_id:
        return HistoricalAudioUsageAvailability(
            False,
            "Historical variant snapshot does not match the grant.",
        )

    snapshot_public_id = str(
        technical.get("variant_public_id") or ""
    ).strip()

    if (
        snapshot_public_id
        and snapshot_public_id
        != str(variant.public_id)
    ):
        return HistoricalAudioUsageAvailability(
            False,
            "Historical variant identity does not match the grant.",
        )

    snapshot_checksum = str(
        technical.get("checksum_sha256") or ""
    ).strip()

    current_checksum = str(
        variant.checksum_sha256 or ""
    ).strip()

    if (
        snapshot_checksum
        and current_checksum
        and snapshot_checksum != current_checksum
    ):
        return HistoricalAudioUsageAvailability(
            False,
            "Historical audio asset no longer matches the granted variant.",
        )

    return HistoricalAudioUsageAvailability(True)