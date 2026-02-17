# apps/subtitles/signals/voice_hooks.py

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.subtitles.models import SubtitleTrack, VoiceTrack, VoiceJobStatus
from apps.subtitles.constants import VOICE_ENABLED_LANGUAGES
from apps.translations.services.language_codes import normalize_language_code
from apps.subtitles.services.voice_resolver import resolve_voice_id
from apps.subtitles.services.ownership import resolve_owner_gender_from_transcript
from apps.subtitles.tasks import generate_voice_task


@receiver(post_save, sender=SubtitleTrack)
def auto_generate_voice_on_subtitle_done(
    sender,
    instance: SubtitleTrack,
    created: bool,
    update_fields: set | None,
    **kwargs,
):
    """
    Canonical Voice auto-generation hook.

    Guarantees:
    - Triggers ONLY when subtitle status becomes DONE
    - NEVER generates voice for source/original language
    - Language-gated (VOICE_ENABLED_LANGUAGES)
    - Stores owner_gender + explicit voice_id deterministically
    - Idempotent (one VoiceTrack per SubtitleTrack + provider)
    - Celery task enqueued ONLY after DB commit
    """

    # -------------------------------------------------
    # 1) React ONLY on DONE transition
    # -------------------------------------------------
    if instance.status != "done":
        return
    if update_fields is not None and "status" not in update_fields:
        return

    # -------------------------------------------------
    # 2) Normalize languages
    # -------------------------------------------------
    target_lang = normalize_language_code(instance.target_language)
    source_lang = normalize_language_code(
        getattr(instance.transcript, "source_language", "") or ""
    )

    if not target_lang:
        return

    # No voice for original/source language
    if target_lang == source_lang:
        return

    # TTS language gate
    if target_lang not in set(VOICE_ENABLED_LANGUAGES):
        return

    # -------------------------------------------------
    # 3) Idempotency (ONE VoiceTrack per SubtitleTrack)
    # -------------------------------------------------
    existing = VoiceTrack.objects.filter(
        subtitle_track=instance,
        provider="openai",
    ).first()

    if existing:
        # Backfill legacy missing fields (do not override if already set)
        changed = False

        if not (existing.owner_gender or "").strip():
            existing.owner_gender = resolve_owner_gender_from_transcript(instance.transcript) or ""
            changed = True

        if not (existing.voice_id or "").strip():
            expected_voice_id = resolve_voice_id(
                target_language=target_lang,
                owner_gender=(existing.owner_gender or "").strip() or None,
            )
            existing.voice_id = expected_voice_id
            changed = True

        if changed:
            existing.save(update_fields=["owner_gender", "voice_id"])

        return

    # -------------------------------------------------
    # 4) Build deterministic owner_gender + voice_id
    # -------------------------------------------------
    owner_gender = resolve_owner_gender_from_transcript(instance.transcript) or ""
    voice_id = resolve_voice_id(
        target_language=target_lang,
        owner_gender=owner_gender or None,
    )

    # -------------------------------------------------
    # 5) Create VoiceTrack (PENDING)
    # -------------------------------------------------
    voice = VoiceTrack.objects.create(
        transcript=instance.transcript,
        subtitle_track=instance,
        target_language=target_lang,
        owner_gender=owner_gender,
        provider="openai",
        voice_id=voice_id,                 # explicit from day 1 ✅
        status=VoiceJobStatus.PENDING,
        spoken_text="",
    )

    # -------------------------------------------------
    # 6) Enqueue AFTER transaction commit ✅
    # -------------------------------------------------
    transaction.on_commit(lambda: generate_voice_task.delay(voice.id))
