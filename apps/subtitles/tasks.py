# apps/subtitles/tasks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

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
    SubtitleJobStatus,
    TranscriptContentReviewStatus,
    TranscriptDetectedContentType,
)
from apps.subtitles.services.stt_openai import transcribe_audio
from apps.subtitles.services.subtitle_builder import build_subtitle_track
from apps.subtitles.services.orchestrator import enqueue_default_subtitles
from apps.translations.services.language_codes import normalize_language_code
from apps.subtitles.services.voice_tone import build_tone_profile_from_stt
from apps.subtitles.services.voice_resolver import resolve_voice_id
from apps.subtitles.services.ownership import resolve_owner_gender_from_transcript
from apps.subtitles.services.testimony_review import (
    review_and_update_transcript,
    assert_transcript_ai_allowed,
)
from apps.subtitles.services.testimony_enforcement import (
    enforce_testimony_review_outcome,
)

from apps.accounts.constants.gender import MALE, FEMALE

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

    # Guard expensive subtitle generation.
    assert_transcript_ai_allowed(transcript)

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
        → STT raw
        → early testimony review gate
        → if rejected: delete testimony media
        → if needs_review: keep raw transcript for admin review only
        → if approved: LLM cleanup + segments + subtitles
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
        # 3) Speech-to-Text raw
        # -------------------------------------------------
        stt = transcribe_audio(wav_path=local_audio_path)
        tone_profile = build_tone_profile_from_stt(stt)

        raw_lang = stt.get("language", "") or ""
        source_lang = normalize_language_code(raw_lang)
        raw_text = (stt.get("text", "") or "").strip()

        # Save raw transcript first so admin/debug has something if needed.
        transcript.source_language = source_lang
        transcript.tone_profile = tone_profile
        transcript.full_text = raw_text
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
        # 4) Store raw segments before review
        # -------------------------------------------------
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

        TranscriptSegment.objects.filter(transcript=transcript).delete()

        raw_bulk: list[TranscriptSegment] = []

        for idx, (text, meta) in enumerate(zip(raw_segments, segment_meta)):
            raw_bulk.append(
                TranscriptSegment(
                    transcript=transcript,
                    idx=idx,
                    start_ms=meta["start_ms"],
                    end_ms=meta["end_ms"],
                    text=text,
                )
            )

        if raw_bulk:
            TranscriptSegment.objects.bulk_create(raw_bulk, batch_size=500)

        # -------------------------------------------------
        # 5) Cheap local rejection before OpenAI review
        # -------------------------------------------------
        word_count = len(raw_text.split())

        if not raw_text or word_count < 4 or not raw_segments:
            transcript.content_review_status = TranscriptContentReviewStatus.REJECTED
            transcript.detected_content_type = TranscriptDetectedContentType.UNKNOWN
            transcript.content_review_confidence = 1.0
            transcript.content_review_reason = "Transcript contains no discernible content."
            transcript.ai_processing_allowed = False
            transcript.content_reviewed_at = timezone.now()
            transcript.updated_at = timezone.now()
            transcript.save(
                update_fields=[
                    "content_review_status",
                    "detected_content_type",
                    "content_review_confidence",
                    "content_review_reason",
                    "ai_processing_allowed",
                    "content_reviewed_at",
                    "updated_at",
                ]
            )

            outcome = enforce_testimony_review_outcome(transcript)

            if outcome == "deleted":
                logger.warning(
                    "🚫 Rejected testimony removed after local transcript guard transcript=%s",
                    transcript_id,
                )
                return transcript_id

            return transcript.id
        
        # -------------------------------------------------
        # 6) Early review before expensive cleanup/subtitle/voice jobs
        # -------------------------------------------------
        transcript.refresh_from_db()
        transcript = review_and_update_transcript(transcript)

        outcome = enforce_testimony_review_outcome(transcript)

        if outcome == "deleted":
            logger.warning(
                "🚫 Rejected testimony removed after early transcript review transcript=%s",
                transcript_id,
            )
            return transcript_id

        if outcome == "needs_review":

            return transcript.id

        if not transcript.ai_processing_allowed:
            logger.info(
                "🚫 Testimony AI pipeline blocked transcript=%s status=%s type=%s confidence=%s",
                transcript.id,
                transcript.content_review_status,
                transcript.detected_content_type,
                transcript.content_review_confidence,
            )
            return transcript.id

        # -------------------------------------------------
        # 7) Approved only: cleanup source transcript
        # -------------------------------------------------
        from apps.subtitles.services.source_humanizer import (
            humanize_transcript_text,
        )

        clean_text = humanize_transcript_text(
            text=raw_text,
            language=source_lang,
        )

        transcript.full_text = clean_text
        transcript.updated_at = timezone.now()
        transcript.save(
            update_fields=[
                "full_text",
                "updated_at",
            ]
        )

        # -------------------------------------------------
        # 8) Approved only: cleanup segments
        # -------------------------------------------------
        from apps.subtitles.services.segment_humanizer import (
            humanize_segments_text,
        )

        clean_segments = humanize_segments_text(
            language=source_lang,
            segments=raw_segments,
        )

        # Safety fallback
        if len(clean_segments) != len(raw_segments):
            clean_segments = raw_segments

        TranscriptSegment.objects.filter(transcript=transcript).delete()

        clean_bulk: list[TranscriptSegment] = []

        for idx, (text, meta) in enumerate(zip(clean_segments, segment_meta)):
            clean_bulk.append(
                TranscriptSegment(
                    transcript=transcript,
                    idx=idx,
                    start_ms=meta["start_ms"],
                    end_ms=meta["end_ms"],
                    text=text,
                )
            )

        if clean_bulk:
            TranscriptSegment.objects.bulk_create(clean_bulk, batch_size=500)

        # -------------------------------------------------
        # 9) Approved only: trigger subtitle generation
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

    # Guard expensive voice generation.
    assert_transcript_ai_allowed(track.transcript)
    
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

# ---------------------------------------------------------------------
# Organization Church Teaching Subtitles
# ---------------------------------------------------------------------
@shared_task(
    queue="subtitles",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def prepare_organization_subtitles_for_video(
    self,
    *,
    content_type_id: int,
    object_id: int,
) -> int:
    """Extract STT audio from converted Church teaching video."""

    import hashlib

    from django.contrib.contenttypes.models import ContentType
    from django.core.files.storage import default_storage

    from apps.media_conversion.services.storage_cleanup import (
        delete_storage_key,
    )
    from apps.subtitles.models import (
        TranscriptContentReviewStatus,
        TranscriptDetectedContentType,
        TranscriptJobStatus,
        VideoTranscript,
    )
    from apps.subtitles.services.audio_asset import build_stt_audio_from_source_video
    from apps.subtitles.services.organization_orchestrator import (
        is_organization_subtitle_target,
    )

    content_type = ContentType.objects.get(pk=content_type_id)
    model_class = content_type.model_class()

    if model_class is None:
        raise RuntimeError("Organization subtitle target model is unavailable.")

    target = model_class._base_manager.get(pk=object_id)

    if not is_organization_subtitle_target(target):
        raise RuntimeError("Target is not eligible for Organization subtitles.")

    if not getattr(target, "is_converted", False):
        raise RuntimeError("Organization teaching video is not converted yet.")

    source_path = str(
        getattr(getattr(target, "video", None), "name", "") or ""
    ).strip().lstrip("/")

    if not source_path.lower().endswith(".m3u8"):
        raise RuntimeError("Organization teaching video HLS source is unavailable.")

    generation = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:20]
    stt_path = (
        f"subtitles/stt/organization_teaching/"
        f"{content_type_id}/{object_id}/{generation}.wav"
    )

    transcript, _ = VideoTranscript.objects.get_or_create(
        content_type=content_type,
        object_id=object_id,
        defaults={"status": TranscriptJobStatus.PENDING},
    )

    existing_audio = str(
        getattr(getattr(transcript, "stt_audio", None), "name", "") or ""
    ).strip().lstrip("/")

    if existing_audio == stt_path and default_storage.exists(stt_path):
        if transcript.status == TranscriptJobStatus.DONE:
            from apps.subtitles.services.organization_orchestrator import (
                enqueue_organization_default_subtitles,
            )
            enqueue_organization_default_subtitles(transcript)
            return transcript.pk

        if transcript.status == TranscriptJobStatus.RUNNING:
            return transcript.pk

        transcript.status = TranscriptJobStatus.PENDING
        transcript.error = ""
        transcript.save(update_fields=["status", "error", "updated_at"])

        build_organization_transcript_for_video.delay(transcript_id=transcript.pk)
        return transcript.pk

    if transcript.voice_tracks.exists():
        raise RuntimeError(
            "Organization subtitle transcript unexpectedly contains voice tracks."
        )

    if existing_audio:
        try:
            if default_storage.exists(existing_audio):
                delete_storage_key(
                    existing_audio,
                    label="organization-subtitles.old-stt-audio",
                )
        except Exception:
            logger.exception(
                "organization_subtitles.old_stt_audio_cleanup_failed transcript=%s",
                transcript.pk,
            )

    transcript.segments.all().delete()
    transcript.subtitle_tracks.all().delete()

    try:
        if default_storage.exists(stt_path):
            delete_storage_key(
                stt_path,
                label="organization-subtitles.stale-stt-generation",
            )
    except Exception:
        logger.exception(
            "organization_subtitles.stt_generation_cleanup_failed path=%s",
            stt_path,
        )

    build_stt_audio_from_source_video(
        source_path=source_path,
        out_rel_path=stt_path,
    )

    transcript.stt_audio.name = stt_path
    transcript.stt_audio_format = "wav"
    transcript.status = TranscriptJobStatus.PENDING
    transcript.error = ""
    transcript.source_language = ""
    transcript.full_text = ""
    transcript.tone_profile = {}
    transcript.content_review_status = TranscriptContentReviewStatus.APPROVED
    transcript.detected_content_type = TranscriptDetectedContentType.TEACHING
    transcript.content_review_confidence = 1.0
    transcript.content_review_reason = (
        "Organization Church teaching subtitle-only pipeline; "
        "Testimony content classification is not applicable."
    )
    transcript.ai_processing_allowed = True
    transcript.content_reviewed_at = timezone.now()
    transcript.save(
        update_fields=[
            "stt_audio",
            "stt_audio_format",
            "status",
            "error",
            "source_language",
            "full_text",
            "tone_profile",
            "content_review_status",
            "detected_content_type",
            "content_review_confidence",
            "content_review_reason",
            "ai_processing_allowed",
            "content_reviewed_at",
            "updated_at",
        ]
    )

    build_organization_transcript_for_video.delay(transcript_id=transcript.pk)
    return transcript.pk


@shared_task(
    queue="subtitles",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def build_organization_transcript_for_video(
    self,
    *,
    transcript_id: int,
) -> int:
    """Build Organization transcript and subtitles without Testimony review or TTS."""

    from apps.subtitles.models import TranscriptJobStatus, TranscriptSegment, VideoTranscript
    from apps.subtitles.services.audio_source import fetch_audio_from_storage
    from apps.subtitles.services.organization_orchestrator import (
        assert_organization_subtitle_transcript,
        enqueue_organization_default_subtitles,
    )
    from apps.subtitles.services.stt_openai import transcribe_audio
    from apps.translations.services.language_codes import normalize_language_code

    transcript = VideoTranscript.objects.select_related("content_type").get(pk=transcript_id)
    assert_organization_subtitle_transcript(transcript)

    if transcript.status == TranscriptJobStatus.DONE:
        enqueue_organization_default_subtitles(transcript)
        return transcript.pk

    if not transcript.stt_audio or not transcript.stt_audio.name:
        raise RuntimeError("Organization STT audio is unavailable.")

    transcript.status = TranscriptJobStatus.RUNNING
    transcript.error = ""
    transcript.save(update_fields=["status", "error", "updated_at"])

    local_audio_path = None

    try:
        local_audio_path = fetch_audio_from_storage(transcript.stt_audio)
        stt = transcribe_audio(wav_path=local_audio_path)

        source_language = normalize_language_code(stt.get("language", "") or "")
        full_text = str(stt.get("text", "") or "").strip()

        rows = []
        for raw_segment in stt.get("segments", []) or []:
            text = str(raw_segment.get("text", "") or "").strip()
            if not text:
                continue

            rows.append(
                TranscriptSegment(
                    transcript=transcript,
                    idx=len(rows),
                    start_ms=int(float(raw_segment["start"]) * 1000),
                    end_ms=int(float(raw_segment["end"]) * 1000),
                    text=text,
                )
            )

        TranscriptSegment.objects.filter(transcript=transcript).delete()
        if rows:
            TranscriptSegment.objects.bulk_create(rows, batch_size=500)

        transcript.source_language = source_language
        transcript.full_text = full_text
        transcript.stt_model = str(stt.get("model", "") or "")
        transcript.status = TranscriptJobStatus.DONE
        transcript.error = ""
        transcript.save(
            update_fields=[
                "source_language",
                "full_text",
                "stt_model",
                "status",
                "error",
                "updated_at",
            ]
        )

        if rows:
            enqueue_organization_default_subtitles(transcript)

        return transcript.pk

    except Exception as exc:
        transcript.status = TranscriptJobStatus.FAILED
        transcript.error = str(exc)
        transcript.save(update_fields=["status", "error", "updated_at"])
        raise

    finally:
        try:
            if local_audio_path and os.path.exists(local_audio_path):
                os.remove(local_audio_path)
        except Exception:
            logger.exception(
                "organization_subtitles.local_audio_cleanup_failed transcript=%s",
                transcript_id,
            )


@shared_task(
    queue="subtitles",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
)
def generate_organization_subtitles_task(
    self,
    *,
    transcript_id: int,
    target_language: str,
    fmt: str = "vtt",
) -> int:
    """Render Organization subtitles only. VoiceTrack generation is never scheduled."""

    from apps.subtitles.models import TranscriptJobStatus, VideoTranscript
    from apps.subtitles.services.organization_orchestrator import (
        assert_organization_subtitle_transcript,
    )
    from apps.subtitles.services.subtitle_builder import build_subtitle_track

    transcript = VideoTranscript.objects.select_related("content_type").get(pk=transcript_id)
    assert_organization_subtitle_transcript(transcript)

    if transcript.status != TranscriptJobStatus.DONE:
        raise RuntimeError("Organization transcript is not ready.")

    track = build_subtitle_track(
        transcript=transcript,
        target_language=target_language,
        fmt=fmt,
    )

    return track.pk
