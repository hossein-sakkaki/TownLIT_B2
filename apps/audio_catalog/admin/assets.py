# apps/audio_catalog/admin/assets.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-03.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from collections import Counter

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicTrack,
    MusicTrackVariant,
)

from .shared import (
    HiddenFromAdminIndexMixin,
    LargeResultAdminMixin,
    conversion_status_badge,
    linked_object,
    render_audio_player,
    render_conversion_job,
    render_image_preview,
    render_json,
)


def _lock_track(track_id: int) -> None:
    MusicTrack.objects.select_for_update().only("pk").get(pk=track_id)


@admin.action(description="Set selected artwork as primary")
def set_as_primary_artwork(modeladmin, request, queryset):
    items = list(queryset.select_related("track"))
    counts = Counter(item.track_id for item in items)
    conflicts = {track_id for track_id, count in counts.items() if count > 1}

    updated = 0
    now = timezone.now()

    for artwork in items:
        if artwork.track_id in conflicts:
            continue

        with transaction.atomic():
            _lock_track(artwork.track_id)

            MusicArtwork.objects.filter(
                track_id=artwork.track_id,
                is_primary=True,
            ).exclude(pk=artwork.pk).update(
                is_primary=False,
                updated_at=now,
            )

            MusicArtwork.objects.filter(pk=artwork.pk).update(
                is_primary=True,
                is_active=True,
                updated_at=now,
            )

        updated += 1

    if updated:
        modeladmin.message_user(
            request,
            f"{updated} artwork(s) set as primary.",
            level=messages.SUCCESS,
        )

    if conflicts:
        modeladmin.message_user(
            request,
            (
                f"Skipped {len(conflicts)} track(s) because more than "
                "one artwork from the same track was selected."
            ),
            level=messages.ERROR,
        )


@admin.action(description="Activate selected artwork")
def activate_artwork(modeladmin, request, queryset):
    count = queryset.update(
        is_active=True,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} artwork(s) activated.",
        level=messages.SUCCESS,
    )


@admin.action(description="Deactivate selected artwork")
def deactivate_artwork(modeladmin, request, queryset):
    count = queryset.update(
        is_active=False,
        is_primary=False,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} artwork(s) deactivated.",
        level=messages.WARNING,
    )


@admin.register(MusicArtwork)
class MusicArtworkAdmin(
    HiddenFromAdminIndexMixin,
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "artwork_thumbnail",
        "track_link",
        "role",
        "is_primary",
        "is_active",
        "conversion_state",
        "conversion_job",
        "updated_at",
    )
    list_display_links = ("artwork_thumbnail",)
    list_filter = (
        "role",
        "is_primary",
        "is_active",
        "is_converted",
        "track__catalog",
        "created_at",
    )
    search_fields = (
        "track__title",
        "track__slug",
        "label",
        "public_id",
    )
    autocomplete_fields = ("track",)
    readonly_fields = (
        "public_id",
        "large_preview",
        "conversion_state",
        "conversion_job",
        "media_assets_pretty",
        "created_at",
        "updated_at",
    )
    actions = (
        set_as_primary_artwork,
        activate_artwork,
        deactivate_artwork,
    )
    list_select_related = (
        "track",
        "track__catalog",
    )
    ordering = ("-created_at", "-id")

    fieldsets = (
        (
            "Artwork",
            {
                "fields": (
                    "track",
                    ("role", "label"),
                    "image",
                    "large_preview",
                ),
            },
        ),
        (
            "State",
            {
                "fields": (
                    ("is_primary", "is_active", "sort_order"),
                    ("conversion_state", "conversion_job"),
                ),
            },
        ),
        (
            "Presentation metadata",
            {
                "fields": (
                    ("width", "height", "aspect_ratio"),
                    ("dominant_color", "blurhash"),
                ),
            },
        ),
        (
            "Media manifest",
            {
                "classes": ("collapse",),
                "fields": (
                    "media_assets_pretty",
                    "public_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            _lock_track(obj.track_id)

            if obj.is_primary:
                obj.is_active = True

                MusicArtwork.objects.filter(
                    track_id=obj.track_id,
                    is_primary=True,
                ).exclude(pk=obj.pk).update(
                    is_primary=False,
                    updated_at=timezone.now(),
                )

            super().save_model(request, obj, form, change)

    @admin.display(description="Artwork")
    def artwork_thumbnail(self, obj):
        return render_image_preview(obj.image, width=58, height=58)

    @admin.display(description="Track", ordering="track__title")
    def track_link(self, obj):
        return linked_object(obj.track)

    @admin.display(description="Preview")
    def large_preview(self, obj):
        return render_image_preview(obj.image, width=360, height=360)

    @admin.display(description="Conversion")
    def conversion_state(self, obj):
        return conversion_status_badge(obj)

    @admin.display(description="Latest job")
    def conversion_job(self, obj):
        return render_conversion_job(obj)

    @admin.display(description="Media assets")
    def media_assets_pretty(self, obj):
        return render_json(obj.media_assets)


@admin.action(description="Set selected variants as track defaults")
def set_as_default_variant(modeladmin, request, queryset):
    items = list(queryset.select_related("track"))
    counts = Counter(item.track_id for item in items)
    conflicts = {track_id for track_id, count in counts.items() if count > 1}

    updated = 0
    now = timezone.now()

    for variant in items:
        if variant.track_id in conflicts:
            continue

        with transaction.atomic():
            _lock_track(variant.track_id)

            MusicTrackVariant.objects.filter(
                track_id=variant.track_id,
                is_default=True,
            ).exclude(pk=variant.pk).update(
                is_default=False,
                updated_at=now,
            )

            MusicTrackVariant.objects.filter(pk=variant.pk).update(
                is_default=True,
                is_active=True,
                is_streamable=True,
                updated_at=now,
            )

        updated += 1

    if updated:
        modeladmin.message_user(
            request,
            f"{updated} variant(s) set as default.",
            level=messages.SUCCESS,
        )

    if conflicts:
        modeladmin.message_user(
            request,
            (
                f"Skipped {len(conflicts)} track(s) because more than "
                "one variant from the same track was selected."
            ),
            level=messages.ERROR,
        )


@admin.action(description="Enable streaming for selected variants")
def enable_streaming(modeladmin, request, queryset):
    count = queryset.update(
        is_streamable=True,
        is_active=True,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"Streaming enabled for {count} variant(s).",
        level=messages.SUCCESS,
    )


@admin.action(description="Disable streaming for selected variants")
def disable_streaming(modeladmin, request, queryset):
    count = queryset.update(
        is_streamable=False,
        is_default=False,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"Streaming disabled for {count} variant(s).",
        level=messages.WARNING,
    )


@admin.register(MusicTrackVariant)
class MusicTrackVariantAdmin(
    HiddenFromAdminIndexMixin,
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "track_link",
        "variant_type",
        "label",
        "audio_player",
        "duration_ms",
        "is_default",
        "is_streamable",
        "is_downloadable",
        "conversion_state",
        "conversion_job",
        "updated_at",
    )
    list_display_links = ("variant_type", "label")
    list_filter = (
        "variant_type",
        "is_default",
        "is_streamable",
        "is_downloadable",
        "is_active",
        "is_converted",
        "track__catalog",
        "created_at",
    )
    search_fields = (
        "track__title",
        "track__slug",
        "label",
        "public_id",
        "checksum_sha256",
    )
    autocomplete_fields = ("track",)
    readonly_fields = (
        "public_id",
        "audio_player_large",
        "conversion_state",
        "conversion_job",
        "media_assets_pretty",
        "created_at",
        "updated_at",
    )
    actions = (
        set_as_default_variant,
        enable_streaming,
        disable_streaming,
    )
    list_select_related = (
        "track",
        "track__catalog",
    )
    ordering = ("-created_at", "-id")

    fieldsets = (
        (
            "Track and variant",
            {
                "fields": (
                    "track",
                    ("variant_type", "label", "locale"),
                    "audio_file",
                    "audio_player_large",
                ),
            },
        ),
        (
            "Playback",
            {
                "fields": (
                    (
                        "is_default",
                        "is_streamable",
                        "is_downloadable",
                        "is_active",
                    ),
                    ("duration_ms", "source_start_ms", "source_end_ms"),
                ),
            },
        ),
        (
            "Technical metadata",
            {
                "fields": (
                    ("mime_type", "codec", "container"),
                    ("bitrate_kbps", "sample_rate_hz", "channels"),
                    ("file_size_bytes", "checksum_sha256"),
                ),
            },
        ),
        (
            "Conversion",
            {
                "fields": (
                    "conversion_state",
                    "conversion_job",
                ),
            },
        ),
        (
            "Advanced",
            {
                "classes": ("collapse",),
                "fields": (
                    "waveform_file",
                    "sort_order",
                    "metadata",
                    "media_assets_pretty",
                    "public_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            _lock_track(obj.track_id)

            if obj.is_default:
                obj.is_active = True
                obj.is_streamable = True

                MusicTrackVariant.objects.filter(
                    track_id=obj.track_id,
                    is_default=True,
                ).exclude(pk=obj.pk).update(
                    is_default=False,
                    updated_at=timezone.now(),
                )

            super().save_model(request, obj, form, change)

    @admin.display(description="Track", ordering="track__title")
    def track_link(self, obj):
        return linked_object(obj.track)

    @admin.display(description="Listen")
    def audio_player(self, obj):
        return render_audio_player(obj.audio_file, width=230)

    @admin.display(description="Audio preview")
    def audio_player_large(self, obj):
        return render_audio_player(obj.audio_file, width=600)

    @admin.display(description="Conversion")
    def conversion_state(self, obj):
        return conversion_status_badge(obj)

    @admin.display(description="Latest job")
    def conversion_job(self, obj):
        return render_conversion_job(obj)

    @admin.display(description="Media assets")
    def media_assets_pretty(self, obj):
        return render_json(obj.media_assets)