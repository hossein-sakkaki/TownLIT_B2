# apps/audio_catalog/services/historical_usage.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from dataclasses import dataclass

from apps.audio_catalog.models import AudioUsageGrant


@dataclass(frozen=True)
class HistoricalAudioUsageAvailability:
    allowed: bool
    reason: str = ""


def can_render_existing_audio_usage(grant: AudioUsageGrant):
    if grant.status != AudioUsageGrant.Status.ACTIVE:
        return HistoricalAudioUsageAvailability(False, "Audio usage grant is not active.")
    snapshot = grant.rights_snapshot if isinstance(grant.rights_snapshot, dict) else {}
    if not snapshot.get("perpetual_existing_content_allowed", False):
        return HistoricalAudioUsageAvailability(False, "Historical use is not preserved by the grant snapshot.")
    if grant.variant_id:
        technical = grant.technical_snapshot if isinstance(grant.technical_snapshot, dict) else {}
        if int(technical.get("variant_id") or 0) != grant.variant_id:
            return HistoricalAudioUsageAvailability(False, "Historical variant snapshot does not match the grant.")
    return HistoricalAudioUsageAvailability(True)
