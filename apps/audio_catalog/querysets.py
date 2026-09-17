# apps/audio_catalog/querysets.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from __future__ import annotations

from django.db.models import F, Prefetch, Q
from django.utils import timezone

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicTrack,
    MusicTrackVariant,
)
from apps.organizations.constants import (
    OrganizationModuleActivationStatus,
    OrganizationStatus,
)
from apps.organizations.modules.worship.constants import (
    OrganizationMusicContributionStatus,
    OrganizationMusicLicenseStatus,
)


def _current_organization_origin_filter(now):
    current_origin = (
        Q(
            organization_music_contribution__status=(
                OrganizationMusicContributionStatus.PUBLISHED
            ),
            organization_music_contribution__rights_record_id=F(
                "rights__id"
            ),
            organization_music_contribution__license__status=(
                OrganizationMusicLicenseStatus.ACTIVE
            ),
            organization_music_contribution__workspace__activation__organization__status=(
                OrganizationStatus.ACTIVE
            ),
            organization_music_contribution__workspace__activation__status=(
                OrganizationModuleActivationStatus.ENABLED
            ),
        )
        & (
            Q(
                organization_music_contribution__license__effective_from__isnull=True
            )
            | Q(
                organization_music_contribution__license__effective_from__lte=now
            )
        )
        & (
            Q(
                organization_music_contribution__license__effective_until__isnull=True
            )
            | Q(
                organization_music_contribution__license__effective_until__gt=now
            )
        )
        & Q(
            organization_music_contribution__license__workspace_id=F(
                "organization_music_contribution__workspace_id"
            )
        )
    )

    return (
        Q(organization_music_contribution__isnull=True)
        | current_origin
    )


def published_tracks():
    now = timezone.now()

    artworks = (
        MusicArtwork.objects
        .filter(
            is_active=True,
            is_converted=True,
        )
        .order_by(
            "sort_order",
            "-is_primary",
            "id",
        )
    )

    variants = (
        MusicTrackVariant.objects
        .filter(
            is_active=True,
            is_converted=True,
            is_streamable=True,
        )
        .order_by(
            "sort_order",
            "-is_default",
            "variant_type",
            "id",
        )
    )

    return (
        MusicTrack.objects
        .filter(
            status=MusicTrack.Status.PUBLISHED,
            is_test_asset=False,
            is_explicit=False,
            allow_streaming=True,
            published_at__lte=now,
            catalog__is_active=True,
            rights__status="cleared",
            rights__streaming_allowed=True,
        )
        .filter(
            Q(rights__effective_from__isnull=True)
            | Q(rights__effective_from__lte=now)
        )
        .filter(
            Q(rights__effective_until__isnull=True)
            | Q(rights__effective_until__gt=now)
        )
        .filter(
            _current_organization_origin_filter(now)
        )
        .select_related(
            "catalog",
            "rights",
            "analytics_metric",
        )
        .prefetch_related(
            "categories",
            "genres",
            "moods",
            "tags",
            "contributor_links__contributor",
            Prefetch(
                "artworks",
                queryset=artworks,
            ),
            Prefetch(
                "variants",
                queryset=variants,
            ),
        )
    )