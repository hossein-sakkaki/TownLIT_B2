# apps/subtitles/selectors.py

from apps.subtitles.models import SubtitleTrack


def get_tracks_for_transcript(transcript_id: int):
    """Return all subtitle tracks for a transcript."""
    return (
        SubtitleTrack.objects
        .filter(transcript_id=transcript_id)
        .order_by("target_language", "fmt")
    )
