# apps/audio_catalog/management/commands/check_audio_mysql_invariants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from apps.audio_catalog.models import AudioUsageGrant, MusicArtwork, MusicTrackVariant

class Command(BaseCommand):
    help = "Check rows that must be unique before MySQL slot constraints are migrated."
    def handle(self,*args,**options):
        checks=(
            ("active primary artwork", MusicArtwork.objects.filter(is_primary=True,is_active=True).values("track_id").annotate(n=Count("id")).filter(n__gt=1), ("track_id",)),
            ("active default variant", MusicTrackVariant.objects.filter(is_default=True,is_active=True).values("track_id").annotate(n=Count("id")).filter(n__gt=1), ("track_id",)),
            ("active usage grant", AudioUsageGrant.objects.filter(status=AudioUsageGrant.Status.ACTIVE).values("content_type_id","object_id").annotate(n=Count("id")).filter(n__gt=1), ("content_type_id","object_id")),
        )
        failed=False
        for label,qs,keys in checks:
            rows=list(qs)
            if rows:
                failed=True; self.stderr.write(f"DUPLICATE {label}: {rows}")
            else: self.stdout.write(self.style.SUCCESS(f"OK: {label}"))
        if failed: raise CommandError("Audio Catalog contains duplicate rows. Resolve explicitly before Phase 8B migration; nothing was modified.")
        self.stdout.write(self.style.SUCCESS("AUDIO MYSQL INVARIANTS PREFLIGHT: OK"))
