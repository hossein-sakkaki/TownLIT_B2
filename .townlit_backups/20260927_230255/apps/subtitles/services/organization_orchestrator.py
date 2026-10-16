# apps/subtitles/services/organization_orchestrator.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.contrib.contenttypes.models import ContentType

from apps.subtitles.constants import SUBTITLES_PREGENERATED_LANGUAGES
from apps.subtitles.models import (
    SubtitleFormat,
    SubtitleJobStatus,
    SubtitleTrack,
    TranscriptJobStatus,
)
from apps.subtitles.services.transcript_builder import (
    get_or_create_transcript_for_object,
)
from apps.translations.services.language_codes import normalize_language_code


ORGANIZATION_TEACHING_MODEL_LABEL = "posts.churchteachingcontent"


def is_organization_subtitle_target(target) -> bool:
    return bool(
        target
        and getattr(getattr(target, "_meta", None), "label_lower", "")
        == ORGANIZATION_TEACHING_MODEL_LABEL
        and getattr(target, "content_format", "") == "video"
    )


def assert_organization_subtitle_transcript(transcript):
    target = transcript.content_object

    if not is_organization_subtitle_target(target):
        raise RuntimeError(
            "Transcript is not an Organization Church teaching subtitle target."
        )

    return target


def enqueue_organization_subtitles_for_target(target):
    """Persist a retryable transcript row and queue subtitle preparation."""

    if not is_organization_subtitle_target(target):
        return None

    if not getattr(target, "pk", None):
        return None

    # Do not spend STT/translation budget on drafts. Publishing remains
    # independent and starts subtitles asynchronously after media readiness.
    if getattr(target, "status", "") != "published":
        return None

    if not getattr(target, "is_converted", False):
        return None

    video = getattr(target, "video", None)
    source_path = str(getattr(video, "name", "") or "").strip().lstrip("/")

    if not source_path or not source_path.lower().endswith(".m3u8"):
        return None

    transcript = get_or_create_transcript_for_object(target)

    from apps.subtitles.tasks import prepare_organization_subtitles_for_video

    content_type = ContentType.objects.get_for_model(
        target,
        for_concrete_model=False,
    )

    prepare_organization_subtitles_for_video.delay(
        content_type_id=content_type.pk,
        object_id=target.pk,
    )

    return transcript


def enqueue_organization_default_subtitles(transcript) -> None:
    """Queue source and curated translations without creating VoiceTrack rows."""

    assert_organization_subtitle_transcript(transcript)

    from apps.subtitles.tasks import generate_organization_subtitles_task

    languages = []
    source_language = normalize_language_code(
        getattr(transcript, "source_language", "") or ""
    )

    if source_language:
        languages.append(source_language)

    target = assert_organization_subtitle_transcript(transcript)

    # Draft video gets its source-language caption track. Curated translated
    # tracks are pre-generated only after publication to avoid unnecessary cost.
    if getattr(target, "status", "") == "published":
        for raw_language in SUBTITLES_PREGENERATED_LANGUAGES:
            language = normalize_language_code(raw_language)
            if language and language not in languages:
                languages.append(language)

    for language in languages:
        track, created = SubtitleTrack.objects.get_or_create(
            transcript=transcript,
            target_language=language,
            fmt=SubtitleFormat.VTT,
        )

        should_queue = created or track.status == SubtitleJobStatus.FAILED

        if not should_queue:
            continue

        if not created:
            track.status = SubtitleJobStatus.PENDING
            track.error = ""
            track.save(update_fields=["status", "error", "updated_at"])

        generate_organization_subtitles_task.delay(
            transcript_id=transcript.pk,
            target_language=language,
            fmt=SubtitleFormat.VTT,
        )
