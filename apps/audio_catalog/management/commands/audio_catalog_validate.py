# apps/audio_catalog/management/commands/audio_catalog_validate.py
from django.core.management.base import BaseCommand
from apps.audio_catalog.models import MusicTrack
from apps.audio_catalog.services.availability import can_use_track

class Command(BaseCommand):
    help = "Validate published audio catalog tracks."

    def handle(self, *args, **options):
        failures = 0
        for track in MusicTrack.objects.filter(status=MusicTrack.Status.PUBLISHED).select_related("rights").iterator(chunk_size=500):
            result = can_use_track(track)
            if not result.allowed:
                failures += 1
                self.stderr.write(f"{track.id}: {result.reason}")
        if failures:
            self.stderr.write(self.style.ERROR(f"{failures} track(s) failed."))
        else:
            self.stdout.write(self.style.SUCCESS("Audio catalog is valid."))
