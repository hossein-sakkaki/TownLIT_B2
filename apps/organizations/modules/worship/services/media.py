# apps/organizations/modules/worship/services/media.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-07.
# Last Update by Hossein Sakkaki on 2026-09-07.
#

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicTrackVariant,
)
from apps.organizations.modules.worship.constants import (
    OrganizationMusicContributionStatus,
    WorshipAuditEvent,
    WorshipPermissionKey,
)
from apps.organizations.modules.worship.models import (
    OrganizationMusicContribution,
)

from .access import ensure_worship_permission
from .audit import record_worship_audit
from .safety import (
    enforce_worship_music_artwork_safety,
    enforce_worship_music_audio_safety,
    mark_worship_music_asset_safety,
)


def _ensure_draft(contribution):
    if (
        contribution.status
        != OrganizationMusicContributionStatus.DRAFT
    ):
        raise ValidationError(
            "Organization music media can be changed only while the contribution is draft."
        )


@transaction.atomic
def add_organization_music_artwork(
    *,
    contribution,
    actor,
    image,
    role=MusicArtwork.Role.PRIMARY,
    label="",
    is_primary=True,
    sort_order=0,
):
    workspace = contribution.workspace

    ensure_worship_permission(
        actor=actor,
        workspace=workspace,
        permission_key=WorshipPermissionKey.MANAGE_CONTRIBUTIONS,
    )

    _ensure_draft(
        contribution
    )

    enforce_worship_music_artwork_safety(
        actor=actor,
        file_obj=image,
    )

    locked = (
        OrganizationMusicContribution.objects
        .select_for_update()
        .select_related(
            "workspace",
            "track",
        )
        .get(pk=contribution.pk)
    )

    _ensure_draft(
        locked
    )

    make_primary = bool(
        is_primary
        or not locked.track.artworks.filter(
            is_active=True,
            is_primary=True,
        ).exists()
    )

    if make_primary:
        locked.track.artworks.filter(
            is_primary=True,
            is_active=True,
        ).update(
            is_primary=False,
            primary_slot=None,
        )

    artwork = MusicArtwork(
        track=locked.track,
        role=role,
        label=str(label or "").strip(),
        image=image,
        is_active=True,
        is_primary=make_primary,
        sort_order=max(int(sort_order or 0), 0),
    )

    artwork.full_clean()
    artwork.save()

    mark_worship_music_asset_safety(
        contribution=locked,
        kind="artwork",
        public_id=artwork.public_id,
    )

    record_worship_audit(
        workspace=locked.workspace,
        event=WorshipAuditEvent.CONTRIBUTION_CREATED,
        actor=actor,
        entity=locked,
        metadata={
            "operation": "artwork_added",
            "artwork_public_id": str(
                artwork.public_id
            ),
            "role": artwork.role,
            "is_primary": artwork.is_primary,
        },
    )

    return artwork


@transaction.atomic
def add_organization_music_variant(
    *,
    contribution,
    actor,
    audio_file,
    variant_type=MusicTrackVariant.VariantType.PLAYBACK,
    label="",
    locale="",
    is_default=True,
    sort_order=0,
):
    workspace = contribution.workspace

    ensure_worship_permission(
        actor=actor,
        workspace=workspace,
        permission_key=WorshipPermissionKey.MANAGE_CONTRIBUTIONS,
    )

    _ensure_draft(
        contribution
    )

    enforce_worship_music_audio_safety(
        actor=actor,
        file_obj=audio_file,
        has_vocals=contribution.track.has_vocals,
    )

    locked = (
        OrganizationMusicContribution.objects
        .select_for_update()
        .select_related(
            "workspace",
            "track",
        )
        .get(pk=contribution.pk)
    )

    _ensure_draft(
        locked
    )

    make_default = bool(
        is_default
        or not locked.track.variants.filter(
            is_active=True,
            is_default=True,
        ).exists()
    )

    if make_default:
        locked.track.variants.filter(
            is_default=True,
            is_active=True,
        ).update(
            is_default=False,
            default_slot=None,
        )

    variant = MusicTrackVariant(
        track=locked.track,
        variant_type=variant_type,
        label=str(label or "").strip(),
        locale=str(locale or "").strip(),
        audio_file=audio_file,
        is_default=make_default,
        is_streamable=True,
        is_downloadable=False,
        is_offline_eligible=False,
        is_active=True,
        duration_ms=locked.track.duration_ms,
        sort_order=max(int(sort_order or 0), 0),
        metadata={
            "organization_music_contribution": True,
        },
    )

    variant.full_clean()
    variant.save()

    mark_worship_music_asset_safety(
        contribution=locked,
        kind="audio",
        public_id=variant.public_id,
    )

    record_worship_audit(
        workspace=locked.workspace,
        event=WorshipAuditEvent.CONTRIBUTION_CREATED,
        actor=actor,
        entity=locked,
        metadata={
            "operation": "audio_variant_added",
            "variant_public_id": str(
                variant.public_id
            ),
            "variant_type": variant.variant_type,
            "is_default": variant.is_default,
        },
    )

    return variant