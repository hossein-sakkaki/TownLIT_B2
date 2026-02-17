# apps/subtitles/hooks.py

from apps.subtitles.services.transcript_builder import (
    get_or_create_transcript_for_object,
)
from apps.subtitles.tasks import build_transcript_for_video
from apps.subtitles.models import TranscriptJobStatus


# apps/subtitles/hooks.py

def maybe_start_transcript_for_testimony(testimony):
    if testimony.type != testimony.TYPE_VIDEO:
        return

    if not testimony.is_converted:
        return

    transcript = get_or_create_transcript_for_object(testimony)

    # 🚨 NEW GUARD: audio must exist
    if not transcript.stt_audio or not transcript.stt_audio.name:
        return

    if transcript.status in (
        TranscriptJobStatus.DONE,
        TranscriptJobStatus.RUNNING,
    ):
        return

    build_transcript_for_video.delay(transcript.id)
