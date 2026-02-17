# apps/subtitles/tasks.py

from __future__ import annotations

import os
import logging
import shutil

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.files import File

from apps.subtitles.models import (
    VideoTranscript,
    TranscriptSegment,
    TranscriptJobStatus,
    VoiceTrack,
    VoiceJobStatus,
    SubtitleJobStatus
)
from apps.subtitles.services.stt_openai import transcribe_audio
from apps.subtitles.services.subtitle_builder import build_subtitle_track
from apps.subtitles.services.orchestrator import enqueue_default_subtitles
from apps.translations.services.language_codes import normalize_language_code
from apps.subtitles.services.voice_tone import build_tone_profile_from_stt
from apps.subtitles.services.voice_resolver import resolve_voice_id
from apps.subtitles.services.ownership import resolve_owner_gender_from_transcript

from apps.accounts.constants import MALE, FEMALE

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------
# Subtitle Track
# ---------------------------------------------------------------------
@shared_task(
    queue="subtitles",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def generate_subtitles_task(
    self,
    *,
    transcript_id: int,
    target_language: str,
    fmt: str = "vtt",
) -> int:
    """
    Translate segments and render subtitle track.
    Returns subtitle_track_id.
    """
    transcript = VideoTranscript.objects.get(pk=transcript_id)

    if transcript.status != TranscriptJobStatus.DONE:
        raise RuntimeError("Transcript not ready")

    track = build_subtitle_track(
        transcript=transcript,
        target_language=target_language,
        fmt=fmt,
    )

    return track.id


# ---------------------------------------------------------------------
# Transcript Building (STT + CLEANUP)
# ---------------------------------------------------------------------
@shared_task(
    queue="subtitles",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def build_transcript_for_video(self, transcript_id: int) -> int:
    """
    Canonical STT pipeline:

    stored STT audio
        → STT (raw)
        → LLM cleanup 
        → segments (raw timing preserved)
        → subtitle generation
    """
    transcript = VideoTranscript.objects.get(pk=transcript_id)

    # Idempotent
    if transcript.status == TranscriptJobStatus.DONE:
        return transcript.id

    transcript.status = TranscriptJobStatus.RUNNING
    transcript.error = ""
    transcript.updated_at = timezone.now()
    transcript.save(update_fields=["status", "error", "updated_at"])

    local_audio_path: str | None = None

    try:
        # -------------------------------------------------
        # 1) Ensure STT audio exists
        # -------------------------------------------------
        audio_field = transcript.stt_audio
        if not audio_field or not audio_field.name:
            raise RuntimeError("STT audio not available for transcript")

        # -------------------------------------------------
        # 2) Download STT audio from storage
        # -------------------------------------------------
        from apps.subtitles.services.audio_source import fetch_audio_from_storage
        local_audio_path = fetch_audio_from_storage(audio_field)

        # -------------------------------------------------
        # 3) Speech-to-Text (RAW)
        # -------------------------------------------------
        stt = transcribe_audio(wav_path=local_audio_path)
        tone_profile = build_tone_profile_from_stt(stt)

        raw_lang = stt.get("language", "") or ""
        source_lang = normalize_language_code(raw_lang)

        raw_text = stt.get("text", "") or ""

        # -------------------------------------------------
        # 4) CLEANUP source transcript (LLM, conservative)
        # -------------------------------------------------
        from apps.subtitles.services.source_humanizer import (
            humanize_transcript_text, 
        )

        clean_text = humanize_transcript_text(
            text=raw_text,
            language=source_lang,
        )

        transcript.source_language = source_lang
        transcript.tone_profile = tone_profile
        transcript.full_text = clean_text
        transcript.stt_model = stt.get("model", "")
        transcript.status = TranscriptJobStatus.DONE
        transcript.updated_at = timezone.now()
        transcript.save(
            update_fields=[
                "source_language",
                "full_text",
                "stt_model",
                "status",
                "updated_at",
                "tone_profile",
            ]
        )

        # -------------------------------------------------
        # 5) Replace segments (timing-safe + humanized text)
        # -------------------------------------------------
        from apps.subtitles.services.segment_humanizer import (
            humanize_segments_text, 
        )

        raw_segments = []
        segment_meta = []

        for seg in stt.get("segments", []):
            text = (seg.get("text") or "").strip()
            if not text:
                continue

            raw_segments.append(text)
            segment_meta.append({
                "start_ms": int(float(seg["start"]) * 1000),
                "end_ms": int(float(seg["end"]) * 1000),
            })

        # 🔹 Humanize segments in ONE batch (safe)
        clean_segments = humanize_segments_text(
            language=source_lang,
            segments=raw_segments,
        )

        # Safety fallback
        if len(clean_segments) != len(raw_segments):
            clean_segments = raw_segments

        # Replace DB segments
        TranscriptSegment.objects.filter(transcript=transcript).delete()

        bulk: list[TranscriptSegment] = []

        for idx, (text, meta) in enumerate(zip(clean_segments, segment_meta)):
            bulk.append(
                TranscriptSegment(
                    transcript=transcript,
                    idx=idx,
                    start_ms=meta["start_ms"],
                    end_ms=meta["end_ms"],
                    text=text,
                )
            )

        if bulk:
            TranscriptSegment.objects.bulk_create(bulk, batch_size=500)


        # -------------------------------------------------
        # 6) Trigger subtitle generation (source + preset langs)
        # -------------------------------------------------
        enqueue_default_subtitles(transcript)

        return transcript.id

    except Exception as exc:
        transcript.status = TranscriptJobStatus.FAILED
        transcript.error = str(exc)
        transcript.updated_at = timezone.now()
        transcript.save(update_fields=["status", "error", "updated_at"])
        raise

    finally:
        # -------------------------------------------------
        # Cleanup temp audio file
        # -------------------------------------------------
        try:
            if local_audio_path and os.path.exists(local_audio_path):
                os.remove(local_audio_path)
        except Exception:
            pass


# ---------------------------------------------------------------------
# Voice Track (TTS + Voice Humanizer)
# ---------------------------------------------------------------------
@shared_task(
    queue="subtitles",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def generate_voice_task(self, voice_track_id: int) -> int:
    """
    Generate synced TTS audio from Subtitle VTT timeline.

    Policy:
    - voice_id MUST be explicit and stable
    - If voice_id is empty -> set once (legacy repair)
    - If voice_id is set -> NEVER change it (avoid frontend mismatch)
    - owner_gender can be repaired if missing
    """
    try:
        track = VoiceTrack.objects.select_related(
            "subtitle_track",
            "transcript",
        ).get(pk=voice_track_id)
    except VoiceTrack.DoesNotExist:
        raise self.retry(countdown=10, max_retries=5)

    # -------------------------------------------------
    # 1) Idempotency
    # -------------------------------------------------
    if track.status == VoiceJobStatus.DONE and track.audio and track.audio.name:
        return track.id

    track.status = VoiceJobStatus.RUNNING
    track.error = ""
    track.updated_at = timezone.now()
    track.save(update_fields=["status", "error", "updated_at"])

    local_mp3_path: str | None = None

    try:
        # -------------------------------------------------
        # 2) Resolve VTT timeline (source of truth)
        # -------------------------------------------------
        vtt = track.subtitle_track.content or ""
        if not vtt.strip():
            raise RuntimeError("Subtitle VTT content is empty")

        # -------------------------------------------------
        # 3) Legacy repair: owner_gender (only if missing/invalid)
        # -------------------------------------------------
        owner_gender = (track.owner_gender or "").strip()
        if owner_gender not in (MALE, FEMALE):
            owner_gender = resolve_owner_gender_from_transcript(track.transcript) or ""
            track.owner_gender = owner_gender  # store once

        # -------------------------------------------------
        # 4) Legacy repair: voice_id (ONLY if empty)
        # -------------------------------------------------
        current_voice_id = (track.voice_id or "").strip().lower()
        if not current_voice_id:
            expected_voice_id = resolve_voice_id(
                target_language=track.target_language,
                owner_gender=owner_gender or None,
            )
            track.voice_id = expected_voice_id  # set once for old rows

        # Persist repairs before synthesis
        track.save(update_fields=["owner_gender", "voice_id"])

        # -------------------------------------------------
        # 5) Build synced audio from VTT timeline
        # -------------------------------------------------
        from apps.subtitles.services.voice_timeline_builder import (
            build_voice_audio_from_vtt_timeline,
        )

        # Keep spoken_text for debug (optional)
        track.spoken_text = track.spoken_text or ""
        track.save(update_fields=["spoken_text"])

        tone_profile = track.transcript.tone_profile or {}

        local_mp3_path, duration_ms = build_voice_audio_from_vtt_timeline(
            vtt_text=vtt,
            target_language=track.target_language,
            voice_id=track.voice_id,          # explicit, stable ✅
            gender=owner_gender or None,      # passed through ✅
            tone_profile=tone_profile,
        )

        # -------------------------------------------------
        # 6) Save final mp3 using FileUpload (canonical)
        # -------------------------------------------------
        with open(local_mp3_path, "rb") as rf:
            django_file = File(rf, name=os.path.basename(local_mp3_path))
            track.audio.save(
                os.path.basename(local_mp3_path),
                django_file,
                save=False,
            )

        # -------------------------------------------------
        # 7) Finalize
        # -------------------------------------------------
        track.duration_ms = duration_ms
        track.status = VoiceJobStatus.DONE
        track.updated_at = timezone.now()
        track.save(
            update_fields=[
                "audio",
                "duration_ms",
                "status",
                "updated_at",
            ]
        )

        return track.id

    except Exception as exc:
        track.status = VoiceJobStatus.FAILED
        track.error = str(exc)
        track.updated_at = timezone.now()
        track.save(update_fields=["status", "error", "updated_at"])
        raise

    finally:
        # -------------------------------------------------
        # 8) Cleanup temp dir
        # -------------------------------------------------
        try:
            if local_mp3_path:
                tmpdir = os.path.dirname(local_mp3_path)
                if tmpdir and os.path.isdir(tmpdir):
                    shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass