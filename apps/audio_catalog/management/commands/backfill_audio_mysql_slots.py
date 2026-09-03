# apps/audio_catalog/management/commands/backfill_audio_mysql_slots.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.audio_catalog.models import AudioUsageGrant, MusicArtwork, MusicTrackVariant

class Command(BaseCommand):
    help = "Backfill MySQL nullable uniqueness slots after Phase 8B schema migration."
    @transaction.atomic
    def handle(self,*args,**options):
        MusicArtwork.objects.update(primary_slot=None)
        MusicTrackVariant.objects.update(default_slot=None)
        AudioUsageGrant.objects.update(active_slot=None)
        a=MusicArtwork.objects.filter(is_primary=True,is_active=True).update(primary_slot=1)
        v=MusicTrackVariant.objects.filter(is_default=True,is_active=True).update(default_slot=1)
        g=AudioUsageGrant.objects.filter(status=AudioUsageGrant.Status.ACTIVE).update(active_slot=1)
        self.stdout.write(self.style.SUCCESS(f"Backfilled slots: artworks={a}, variants={v}, usage_grants={g}"))
