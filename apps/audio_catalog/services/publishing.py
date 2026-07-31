# apps/audio_catalog/services/publishing.py
from django.db import transaction
from django.utils import timezone
from apps.audio_catalog.models import MusicTrack
from .availability import can_use_track

@transaction.atomic
def publish_track(track, actor=None):
    track = MusicTrack.objects.select_for_update().select_related("rights").get(pk=track.pk)
    track.status = MusicTrack.Status.PUBLISHED
    track.published_at = track.published_at or timezone.now()
    track.updated_by = actor
    result = can_use_track(track)
    if not result.allowed:
        raise ValueError(result.reason)
    track.save(update_fields=("status", "published_at", "updated_by", "updated_at"))
    return track

@transaction.atomic
def suspend_track(track, actor=None):
    track = MusicTrack.objects.select_for_update().get(pk=track.pk)
    track.status = MusicTrack.Status.SUSPENDED
    track.suspended_at = timezone.now()
    track.updated_by = actor
    track.save(update_fields=("status", "suspended_at", "updated_by", "updated_at"))
    return track
