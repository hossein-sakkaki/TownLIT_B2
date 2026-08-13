# apps/posts/services/journeys/publish.py

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models import MusicTrack, MusicTrackVariant
from apps.audio_catalog.services.usage import assign_music_to_content
from apps.creative_editor.models import (
    CreativeComposition,
    CreativeRenderJob,
)
from apps.posts.constants.journeys import (
    JOURNEY_ACTIVE_DURATION_HOURS,
    JOURNEY_DEFAULT_DURATION_MS,
    JOURNEY_MAX_DURATION_MS,
    JOURNEY_MAX_ENTRIES_PER_DAY,
    JOURNEY_MIN_DURATION_MS,
    JourneyEntryMediaType,
    JourneyPaletteMode,
    JourneyVisualSourceType,
)
from apps.posts.models.journey import Journey, JourneyEntry
from apps.posts.services.journeys.music import (
    prepare_journey_music_selection,
    validate_journey_music_video_compatibility,
)
from apps.posts.services.journeys.storage import (
    build_journey_asset_key,
    copy_storage_asset,
    delete_storage_asset,
)
from apps.posts.services.journeys.timezone import (
    local_date_for_timezone,
    resolve_user_timezone_name,
)
from apps.profiles.models.member import Member


@dataclass(frozen=True)
class JourneyPublishResult:
    journey: Journey
    entry: JourneyEntry
    created_journey: bool

@dataclass(frozen=True)
class JourneyRenderAsset:
    media_type: str
    field_name: str
    source_key: str
    destination_kind: str
    mime_type: str
    duration_ms: int | None

def _resolve_visual_source_type(
    composition: CreativeComposition,
) -> str:
    if composition.source_mode == CreativeComposition.SourceMode.UPLOAD:
        return JourneyVisualSourceType.UPLOADED_IMAGE

    if (
        composition.source_mode
        == CreativeComposition.SourceMode.CONTENT_REFERENCE
    ):
        return JourneyVisualSourceType.CONTENT_REFERENCE

    background = (
        composition.document
        .get("canvas", {})
        .get("background", {})
    )

    background_type = str(
        background.get("type") or ""
    ).strip()

    if background_type == "gradient":
        return JourneyVisualSourceType.GRADIENT_BACKGROUND

    return JourneyVisualSourceType.SOLID_BACKGROUND


def _palette_for_date(local_date) -> str:
    """
    Alternate TownLIT visual identities.
    """

    return (
        JourneyPaletteMode.DAWN
        if local_date.toordinal() % 2 == 0
        else JourneyPaletteMode.EVENING
    )


def _validate_member_owner(
    *,
    user,
    owner,
) -> Member:
    if not user or not user.is_authenticated:
        raise ValidationError(
            "Authentication is required."
        )

    if not user.is_member:
        raise ValidationError(
            {
                "owner": (
                    "Only Member users can publish Journey."
                ),
            }
        )

    if not isinstance(owner, Member):
        raise ValidationError(
            {
                "owner": (
                    "The active profile must be a Member profile."
                ),
            }
        )

    if owner.user_id != user.pk:
        raise ValidationError(
            {
                "owner": (
                    "Journey owner does not match the authenticated user."
                ),
            }
        )

    if not owner.is_active:
        raise ValidationError(
            {
                "owner": "Member profile is inactive.",
            }
        )

    return owner


def _validate_render(
    *,
    user,
    composition: CreativeComposition,
    render_job: CreativeRenderJob,
    requested_revision: int,
) -> None:
    if composition.owner_id != user.pk:
        raise ValidationError(
            {
                "composition_id": (
                    "You do not own this composition."
                ),
            }
        )

    if not composition.is_active:
        raise ValidationError(
            {
                "composition_id": "Composition is inactive.",
            }
        )

    if composition.status != CreativeComposition.Status.READY:
        raise ValidationError(
            {
                "composition_id": (
                    "Composition render is not ready."
                ),
            }
        )

    if composition.revision != requested_revision:
        raise ValidationError(
            {
                "composition_revision": (
                    "Composition revision changed."
                ),
            }
        )

    if composition.rendered_revision != requested_revision:
        raise ValidationError(
            {
                "composition_revision": (
                    "Requested revision is not the current rendered revision."
                ),
            }
        )

    if render_job.composition_id != composition.pk:
        raise ValidationError(
            {
                "render_job_id": (
                    "Render job does not belong to this composition."
                ),
            }
        )

    if render_job.requested_revision != requested_revision:
        raise ValidationError(
            {
                "render_job_id": "Render job revision mismatch.",
            }
        )

    if render_job.status != CreativeRenderJob.Status.DONE:
        raise ValidationError(
            {
                "render_job_id": "Render job is not complete.",
            }
        )

    if render_job.document_sha256 != composition.document_sha256:
        raise ValidationError(
            {
                "render_job_id": "Render document hash mismatch.",
            }
        )

    if not render_job.output_path or not render_job.thumbnail_path:
        raise ValidationError(
            {
                "render_job_id": "Render output is unavailable.",
            }
        )

    if not composition.thumbnail:
        raise ValidationError(
            {
                "composition_id": (
                    "Composition thumbnail is unavailable."
                ),
            }
        )

    composition_thumbnail_key = _normalize_storage_key(
        composition.thumbnail.name
    )

    render_thumbnail_key = _normalize_storage_key(
        render_job.thumbnail_path
    )

    if composition_thumbnail_key != render_thumbnail_key:
        raise ValidationError(
            {
                "render_job_id": (
                    "Render job thumbnail does not match "
                    "the current composition thumbnail."
                ),
            }
        )

    _resolve_render_asset(
        composition=composition,
        render_job=render_job,
    )


def _get_composition(
    *,
    composition_id,
) -> CreativeComposition:
    try:
        return (
            CreativeComposition.objects.select_related(
                "source_content_type",
            )
            .get(public_id=composition_id)
        )
    except CreativeComposition.DoesNotExist as exc:
        raise ValidationError(
            {
                "composition_id": "Composition was not found.",
            }
        ) from exc


def _get_render_job(
    *,
    render_job_id,
) -> CreativeRenderJob:
    try:
        return (
            CreativeRenderJob.objects.select_related("composition")
            .get(public_id=render_job_id)
        )
    except CreativeRenderJob.DoesNotExist as exc:
        raise ValidationError(
            {
                "render_job_id": "Render job was not found.",
            }
        ) from exc

def _normalize_storage_key(value) -> str:
    return str(value or "").strip().lstrip("/")


def _resolve_render_asset(
    *,
    composition: CreativeComposition,
    render_job: CreativeRenderJob,
) -> JourneyRenderAsset:
    has_image = bool(composition.rendered_image)
    has_video = bool(composition.rendered_video)

    if has_image == has_video:
        raise ValidationError(
            {
                "composition_id": (
                    "Composition must have exactly one current "
                    "rendered media asset."
                ),
            }
        )

    job_output_key = _normalize_storage_key(
        render_job.output_path
    )

    if has_video:
        source_key = _normalize_storage_key(
            composition.rendered_video.name
        )

        metadata = (
            composition.media_assets
            or {}
        ).get(
            "rendered_video",
            {},
        )

        duration_ms = int(
            metadata.get("duration_ms")
            or 0
        )

        if not source_key:
            raise ValidationError(
                {
                    "composition_id": (
                        "Rendered video is unavailable."
                    ),
                }
            )

        if source_key != job_output_key:
            raise ValidationError(
                {
                    "render_job_id": (
                        "Render job output does not match "
                        "the current rendered video."
                    ),
                }
            )

        if not (
            JOURNEY_MIN_DURATION_MS
            <= duration_ms
            <= JOURNEY_MAX_DURATION_MS
        ):
            raise ValidationError(
                {
                    "composition_id": (
                        "Rendered video duration is outside "
                        "the Journey duration range."
                    ),
                }
            )

        return JourneyRenderAsset(
            media_type=JourneyEntryMediaType.VIDEO,
            field_name="rendered_video",
            source_key=source_key,
            destination_kind="videos",
            mime_type="video/mp4",
            duration_ms=duration_ms,
        )

    source_key = _normalize_storage_key(
        composition.rendered_image.name
    )

    if not source_key:
        raise ValidationError(
            {
                "composition_id": (
                    "Rendered image is unavailable."
                ),
            }
        )

    if source_key != job_output_key:
        raise ValidationError(
            {
                "render_job_id": (
                    "Render job output does not match "
                    "the current rendered image."
                ),
            }
        )

    return JourneyRenderAsset(
        media_type=JourneyEntryMediaType.IMAGE,
        field_name="rendered_image",
        source_key=source_key,
        destination_kind="images",
        mime_type="image/jpeg",
        duration_ms=None,
    )


def _resolve_display_duration_ms(
    *,
    render_asset: JourneyRenderAsset,
    music_selection,
) -> int:
    """
    Resolve the authoritative Journey display duration.

    Video duration always wins when video exists.
    Music controls duration only for image Journeys.
    """

    if (
        render_asset.media_type
        == JourneyEntryMediaType.VIDEO
    ):
        return int(
            render_asset.duration_ms
            or 0
        )

    if music_selection:
        return int(
            music_selection.clip_duration_ms
        )

    return JOURNEY_DEFAULT_DURATION_MS

def _prepare_music_selection(
    *,
    music_track_id,
    music_variant_id,
    music_clip_start_ms,
    music_clip_end_ms,
    music_volume,
    required_duration_ms: int | None = None,
):
    music_values = (
        music_track_id,
        music_variant_id,
        music_clip_start_ms,
        music_clip_end_ms,
    )

    has_music_input = any(
        value is not None
        for value in music_values
    )

    has_complete_music_input = all(
        value is not None
        for value in music_values
    )

    if (
        has_music_input
        and not has_complete_music_input
    ):
        raise ValidationError(
            {
                "music": (
                    "Track, variant, clip start, "
                    "and clip end are required together."
                ),
            }
        )

    if not has_complete_music_input:
        return None

    try:
        track = (
            MusicTrack.objects.select_related(
                "catalog",
                "rights",
            )
            .prefetch_related(
                "contributor_links__contributor",
            )
            .get(
                public_id=music_track_id
            )
        )

    except MusicTrack.DoesNotExist as exc:
        raise ValidationError(
            {
                "music_track_id": (
                    "Music track was not found."
                ),
            }
        ) from exc

    try:
        variant = (
            MusicTrackVariant.objects
            .select_related(
                "track"
            )
            .get(
                public_id=music_variant_id
            )
        )

    except MusicTrackVariant.DoesNotExist as exc:
        raise ValidationError(
            {
                "music_variant_id": (
                    "Music variant was not found."
                ),
            }
        ) from exc

    return prepare_journey_music_selection(
        track=track,
        variant=variant,
        clip_start_ms=music_clip_start_ms,
        clip_end_ms=music_clip_end_ms,
        music_volume=music_volume,
        required_duration_ms=required_duration_ms,
    )


def _build_media_assets(
    *,
    composition: CreativeComposition,
    render_asset: JourneyRenderAsset,
    rendered_key: str,
    thumbnail_key: str,
    revision: int,
) -> dict:
    source_assets = copy.deepcopy(
        composition.media_assets or {}
    )

    source_render = source_assets.get(
        render_asset.field_name
    ) or {}

    source_thumbnail = source_assets.get(
        "thumbnail"
    ) or {}

    rendered_payload = {
        **source_render,
        "key": rendered_key,
        "mime_type": render_asset.mime_type,
        "revision": revision,
    }

    if render_asset.duration_ms is not None:
        rendered_payload["duration_ms"] = (
            render_asset.duration_ms
        )

    return {
        render_asset.field_name: rendered_payload,
        "thumbnail": {
            **source_thumbnail,
            "key": thumbnail_key,
            "mime_type": "image/jpeg",
            "revision": revision,
        },
    }


def _next_available_sequence(
    *,
    journey: Journey,
) -> int:
    """
    Return the first available sequence from 1 to 12.

    The Journey row must already be locked.
    """

    existing_sequences = set(
        JourneyEntry.objects.filter(
            journey=journey,
        ).values_list(
            "sequence",
            flat=True,
        )
    )

    for sequence in range(
        1,
        JOURNEY_MAX_ENTRIES_PER_DAY + 1,
    ):
        if sequence not in existing_sequences:
            return sequence

    raise ValidationError(
        {
            "journey": "Daily Journey limit has been reached.",
            "max_entries": JOURNEY_MAX_ENTRIES_PER_DAY,
        }
    )


def publish_journey_entry(
    *,
    user,
    owner,
    composition_id,
    render_job_id,
    composition_revision: int,
    visibility: str,
    retention_policy: str,
    requested_timezone: str | None = None,
    music_track_id=None,
    music_variant_id=None,
    music_clip_start_ms=None,
    music_clip_end_ms=None,
    music_volume=1,
) -> JourneyPublishResult:
    """
    Publish one immutable Journey entry.
    """

    member = _validate_member_owner(
        user=user,
        owner=owner,
    )

    timezone_name = resolve_user_timezone_name(
        user=user,
        requested_timezone=requested_timezone,
    )

    now = timezone.now()

    local_date = local_date_for_timezone(
        timezone_name=timezone_name,
        value=now,
    )

    composition = _get_composition(
        composition_id=composition_id,
    )

    render_job = _get_render_job(
        render_job_id=render_job_id,
    )

    requested_revision = int(composition_revision)

    _validate_render(
        user=user,
        composition=composition,
        render_job=render_job,
        requested_revision=requested_revision,
    )

    render_asset = _resolve_render_asset(
        composition=composition,
        render_job=render_job,
    )
    
    required_music_duration_ms = (
        int(
            render_asset.duration_ms
            or 0
        )
        if (
            render_asset.media_type
            == JourneyEntryMediaType.VIDEO
        )
        else None
    )

    music_selection = _prepare_music_selection(
        music_track_id=music_track_id,
        music_variant_id=music_variant_id,
        music_clip_start_ms=music_clip_start_ms,
        music_clip_end_ms=music_clip_end_ms,
        music_volume=music_volume,
        required_duration_ms=required_music_duration_ms,
    )

    display_duration_ms = _resolve_display_duration_ms(
        render_asset=render_asset,
        music_selection=music_selection,
    )
    
    copied_rendered_key = None
    copied_thumbnail_key = None

    try:
        with transaction.atomic():
            # Serialize concurrent Journey publishing
            # for the same Member owner.
            locked_member = (
                Member.objects.select_for_update()
                .get(pk=member.pk)
            )

            if (
                not locked_member.is_active
                or locked_member.user_id != user.pk
            ):
                raise ValidationError(
                    {
                        "owner": "Member profile is unavailable.",
                    }
                )

            # Lock and revalidate mutable editor rows.
            try:
                composition = (
                    CreativeComposition.objects.select_for_update()
                    .select_related("source_content_type")
                    .get(public_id=composition_id)
                )
            except CreativeComposition.DoesNotExist as exc:
                raise ValidationError(
                    {
                        "composition_id": "Composition was not found.",
                    }
                ) from exc

            try:
                render_job = (
                    CreativeRenderJob.objects.select_for_update()
                    .select_related("composition")
                    .get(public_id=render_job_id)
                )
            except CreativeRenderJob.DoesNotExist as exc:
                raise ValidationError(
                    {
                        "render_job_id": "Render job was not found.",
                    }
                ) from exc

            _validate_render(
                user=user,
                composition=composition,
                render_job=render_job,
                requested_revision=requested_revision,
            )

            # Idempotency guard:
            # The same immutable composition revision must never
            # create more than one JourneyEntry.
            existing_entry = (
                JourneyEntry.objects
                .select_related("journey")
                .filter(
                    composition_public_id_snapshot=composition.public_id,
                    composition_revision=requested_revision,
                )
                .first()
            )

            if existing_entry is not None:
                return JourneyPublishResult(
                    journey=existing_entry.journey,
                    entry=existing_entry,
                    created_journey=False,
                )

            render_asset = _resolve_render_asset(
                composition=composition,
                render_job=render_job,
            )

            if (
                music_selection
                and render_asset.media_type
                    == JourneyEntryMediaType.VIDEO
            ):
                validate_journey_music_video_compatibility(
                    music_duration_ms=music_selection.clip_duration_ms,
                    video_duration_ms=int(
                        render_asset.duration_ms or 0
                    ),
                )

            display_duration_ms = _resolve_display_duration_ms(
                render_asset=render_asset,
                music_selection=music_selection,
            )
            
            owner_ct = ContentType.objects.get_for_model(
                Member,
                for_concrete_model=False,
            )

            journey = (
                Journey.objects.select_for_update()
                .filter(
                    content_type=owner_ct,
                    object_id=locked_member.pk,
                    local_date=local_date,
                )
                .first()
            )

            created_journey = False

            if journey is None:
                journey = Journey.objects.create(
                    content_type=owner_ct,
                    object_id=locked_member.pk,
                    local_date=local_date,
                    timezone_name=timezone_name,
                    palette_mode=_palette_for_date(local_date),
                    display_seed=local_date.toordinal(),
                )

                created_journey = True

                journey = (
                    Journey.objects.select_for_update()
                    .get(pk=journey.pk)
                )

            sequence = _next_available_sequence(
                journey=journey,
            )

            entry = JourneyEntry.objects.create(
                journey=journey,
                content_type=owner_ct,
                object_id=locked_member.pk,
                sequence=sequence,
                media_type=render_asset.media_type,
                visual_source_type=_resolve_visual_source_type(
                    composition
                ),
                composition=composition,
                render_job=render_job,
                composition_public_id_snapshot=composition.public_id,
                render_job_public_id_snapshot=render_job.public_id,
                composition_revision=requested_revision,
                composition_document_sha256=(
                    composition.document_sha256
                ),
                visibility=visibility,
                retention_policy=retention_policy,
                published_at=now,
                expires_at=(
                    now
                    + timedelta(
                        hours=JOURNEY_ACTIVE_DURATION_HOURS
                    )
                ),
                display_duration_ms=display_duration_ms,
                music_track=(
                    music_selection.track
                    if music_selection
                    else None
                ),
                music_variant=(
                    music_selection.variant
                    if music_selection
                    else None
                ),
                music_clip_start_ms=(
                    music_selection.clip_start_ms
                    if music_selection
                    else None
                ),
                music_clip_end_ms=(
                    music_selection.clip_end_ms
                    if music_selection
                    else None
                ),
                music_volume=(
                    music_selection.music_volume
                    if music_selection
                    else 1
                ),
                music_attribution_text=(
                    music_selection.attribution_text
                    if music_selection
                    else ""
                ),

                # Filled after immutable promotion.
                rendered_image=None,
                rendered_video=None,
                thumbnail="",
            )

            rendered_destination = build_journey_asset_key(
                entry_id=entry.pk,
                kind=render_asset.destination_kind,
                source_key=render_asset.source_key,
            )

            thumbnail_destination = build_journey_asset_key(
                entry_id=entry.pk,
                kind="thumbnails",
                source_key=render_job.thumbnail_path,
            )

            copied_rendered_key = copy_storage_asset(
                source_key=render_asset.source_key,
                destination_key=rendered_destination,
            )

            copied_thumbnail_key = copy_storage_asset(
                source_key=render_job.thumbnail_path,
                destination_key=thumbnail_destination,
            )

            if render_asset.media_type == JourneyEntryMediaType.VIDEO:
                entry.rendered_image = None
                entry.rendered_video = copied_rendered_key
            else:
                entry.rendered_video = None
                entry.rendered_image = copied_rendered_key

            entry.thumbnail = copied_thumbnail_key

            entry.media_assets = _build_media_assets(
                composition=composition,
                render_asset=render_asset,
                rendered_key=copied_rendered_key,
                thumbnail_key=copied_thumbnail_key,
                revision=requested_revision,
            )

            entry.full_clean()

            entry.save(
                update_fields=[
                    "rendered_image",
                    "rendered_video",
                    "thumbnail",
                    "media_assets",
                    "slug",
                    "updated_at",
                ]
            )

            if music_selection:
                try:
                    assign_music_to_content(
                        content_object=entry,
                        selection=music_selection.usage_selection,
                        granted_to=user,
                        country_code=(
                            getattr(user, "country", "") or ""
                        ),
                    )
                except ValueError as exc:
                    raise ValidationError(
                        {
                            "music": str(exc),
                        }
                    ) from exc

        return JourneyPublishResult(
            journey=journey,
            entry=entry,
            created_journey=created_journey,
        )

    except Exception:
        # Compensate storage because S3 is outside
        # the database transaction.
        if copied_rendered_key:
            delete_storage_asset(copied_rendered_key)

        if copied_thumbnail_key:
            delete_storage_asset(copied_thumbnail_key)

        raise