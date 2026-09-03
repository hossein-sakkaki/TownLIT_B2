# apps/audio_catalog/querysets.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from __future__ import annotations
from django.db.models import Prefetch, Q
from django.utils import timezone
from apps.audio_catalog.models import MusicArtwork, MusicTrack, MusicTrackVariant

def published_tracks():
    now=timezone.now()
    artworks=MusicArtwork.objects.filter(is_active=True,is_converted=True).order_by("sort_order","-is_primary","id")
    variants=MusicTrackVariant.objects.filter(is_active=True,is_converted=True,is_streamable=True).order_by("sort_order","-is_default","variant_type","id")
    return (MusicTrack.objects.filter(status=MusicTrack.Status.PUBLISHED,is_test_asset=False,is_explicit=False,published_at__lte=now,catalog__is_active=True,rights__status="cleared",rights__streaming_allowed=True)
        .filter(Q(rights__effective_from__isnull=True)|Q(rights__effective_from__lte=now))
        .filter(Q(rights__effective_until__isnull=True)|Q(rights__effective_until__gt=now))
        .select_related("catalog","rights","analytics_metric")
        .prefetch_related("categories","genres","moods","tags","contributor_links__contributor",Prefetch("artworks",queryset=artworks),Prefetch("variants",queryset=variants)))
