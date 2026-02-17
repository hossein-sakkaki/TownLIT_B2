# apps/subtitles/services/ensure.py

from __future__ import annotations

from django.utils import timezone

from apps.subtitles.models import (
    VoiceTrack,
    VoiceJobStatus,
    SubtitleJobStatus,
)
from apps.subtitles.services.tts_openai import _resolve_voice_id
from apps.translations.services.language_codes import normalize_language_code


def _normalize_gender_for_tts(owner_gender: str | None) -> str | None:
    """
    Map DB gender to TTS gender keys.
    DB: "Male" | "Female" | "" | None
    TTS: "male" | "female" | None
    """
    g = (owner_gender or "").strip().lower()
    if g == "male":
        return "male"
    if g == "female":
        return "female"

    # Accept canonical DB values too
    if g == "m" or g == "man":
        return "male"
    if g == "f" or g == "woman":
        return "female"

    # If your DB stores "Male"/"Female" exactly, lower() already handled it.
    return None


def ensure_voice_track(
    *,
    subtitle_track,
    provider: str = "openai",
    voice_id: str | None = None,          # client hint only (NOT trusted)
    owner_gender: str | None = None,      # "Male" | "Female" | None
    force_retry_failed: bool = False,
) -> VoiceTrack:
    """
    Ensure a VoiceTrack exists for a SubtitleTrack.

    Key policy:
    - Backend resolves an EXPLICIT voice_id deterministically using (language + owner_gender)
    - We do NOT trust client-provided voice_id to avoid mismatch + duplicates
    """

    if subtitle_track.status != SubtitleJobStatus.DONE:
        raise RuntimeError("Subtitle not ready")

    lang = normalize_language_code(subtitle_track.target_language)

    # Resolve explicit voice id (deterministic)
    tts_gender = _normalize_gender_for_tts(owner_gender)
    resolved_voice_id = _resolve_voice_id(
        language=lang,
        voice_id="default",     # force backend policy (never trust client)
        gender=tts_gender,
    )

    track, created = VoiceTrack.objects.get_or_create(
        transcript=subtitle_track.transcript,
        subtitle_track=subtitle_track,
        target_language=lang,
        provider=provider,
        voice_id=resolved_voice_id,
        defaults={
            "status": VoiceJobStatus.PENDING,
            "error": "",
            # Save gender at creation time (debug/consistency)
            "owner_gender": (owner_gender or ""),
        },
    )

    # If gender is missing on an existing track, fill it (safe, non-unique field)
    if not created and owner_gender and not (track.owner_gender or "").strip():
        track.owner_gender = owner_gender
        track.updated_at = timezone.now()
        track.save(update_fields=["owner_gender", "updated_at"])

    # Idempotency fast paths
    if track.status == VoiceJobStatus.DONE and track.audio:
        return track

    if track.status == VoiceJobStatus.RUNNING:
        return track

    if track.status == VoiceJobStatus.FAILED and not force_retry_failed and not created:
        return track

    # Re-queue
    track.status = VoiceJobStatus.PENDING
    track.error = ""
    track.updated_at = timezone.now()
    track.save(update_fields=["status", "error", "updated_at"])

    from apps.subtitles.tasks import generate_voice_task
    generate_voice_task.delay(track.id)

    return track
