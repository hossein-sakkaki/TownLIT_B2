# apps/subtitles/services/transcript_builder.py

from django.contrib.contenttypes.models import ContentType
from apps.subtitles.models import VideoTranscript


def get_or_create_transcript_for_object(obj) -> VideoTranscript:
    """
    Return existing VideoTranscript or create a new one (PENDING).
    """
    ct = ContentType.objects.get_for_model(obj)

    transcript, _ = VideoTranscript.objects.get_or_create(
        content_type=ct,
        object_id=obj.pk,
        defaults={
            "status": "pending",
        },
    )

    return transcript
