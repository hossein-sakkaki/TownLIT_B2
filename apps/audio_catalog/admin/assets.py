# apps/audio_catalog/admin/assets.py

from __future__ import annotations

from django.contrib import admin, messages
from django.db import transaction

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicTrackVariant,
)

from .shared import (
    LargeResultAdminMixin,
    conversion_status_badge,
    linked_object,
    render_audio_player,
    render_conversion_job,
    render_image_preview,
    render_json,
)


@admin.action(
    description="Set selected artwork as primary",
)
def set_as_primary_artwork(
    modeladmin,
    request,
    queryset,
):
    """
    Set each selected artwork as primary for its track.
    """

    count = 0

    for artwork in queryset.select_related(
        "track"
    ).iterator():
        with transaction.atomic():
            MusicArtwork.objects.filter(
                track_id=artwork.track_id,
                is_primary=True,
            ).exclude(
                pk=artwork.pk,
            ).update(
                is_primary=False,
            )

            MusicArtwork.objects.filter(
                pk=artwork.pk,
            ).update(
                is_primary=True,
                is_active=True,
            )

            count += 1

    modeladmin.message_user(
        request,
        f"{count} artwork(s) set as primary.",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Activate selected artwork",
)
def activate_artwork(
    modeladmin,
    request,
    queryset,
):
    count = queryset.update(
        is_active=True,
    )

    modeladmin.message_user(
        request,
        f"{count} artwork(s) activated.",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Deactivate selected artwork",
)
def deactivate_artwork(
    modeladmin,
    request,
    queryset,
):
    count = queryset.update(
        is_active=False,
        is_primary=False,
    )

    modeladmin.message_user(
        request,
        f"{count} artwork(s) deactivated.",
        level=messages.WARNING,
    )


@admin.register(MusicArtwork)
class MusicArtworkAdmin(
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

    list_display_links = (
        "artwork_thumbnail",
    )

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

    autocomplete_fields = (
        "track",
    )

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

    ordering = (
        "-created_at",
        "-id",
    )

    fieldsets = (
        (
            "Artwork",
            {
                "fields": (
                    "track",
                    (
                        "role",
                        "label",
                    ),
                    "image",
                    "large_preview",
                ),
            },
        ),
        (
            "State",
            {
                "fields": (
                    (
                        "is_primary",
                        "is_active",
                        "sort_order",
                    ),
                    (
                        "conversion_state",
                        "conversion_job",
                    ),
                ),
            },
        ),
        (
            "Presentation metadata",
            {
                "fields": (
                    (
                        "width",
                        "height",
                        "aspect_ratio",
                    ),
                    (
                        "dominant_color",
                        "blurhash",
                    ),
                ),
            },
        ),
        (
            "Media manifest",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "media_assets_pretty",
                    "public_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="Artwork",
    )
    def artwork_thumbnail(self, obj):
        return render_image_preview(
            obj.image,
            width=58,
            height=58,
        )

    @admin.display(
        description="Track",
        ordering="track__title",
    )
    def track_link(self, obj):
        return linked_object(
            obj.track,
        )

    @admin.display(
        description="Preview",
    )
    def large_preview(self, obj):
        return render_image_preview(
            obj.image,
            width=360,
            height=360,
        )

    @admin.display(
        description="Conversion",
    )
    def conversion_state(self, obj):
        return conversion_status_badge(obj)

    @admin.display(
        description="Latest job",
    )
    def conversion_job(self, obj):
        return render_conversion_job(obj)

    @admin.display(
        description="Media assets",
    )
    def media_assets_pretty(self, obj):
        return render_json(
            obj.media_assets
        )


@admin.action(
    description="Set selected variants as track defaults",
)
def set_as_default_variant(
    modeladmin,
    request,
    queryset,
):
    """
    Set selected variants as default per track.
    """

    count = 0

    for variant in queryset.select_related(
        "track"
    ).iterator():
        with transaction.atomic():
            MusicTrackVariant.objects.filter(
                track_id=variant.track_id,
                is_default=True,
            ).exclude(
                pk=variant.pk,
            ).update(
                is_default=False,
            )

            MusicTrackVariant.objects.filter(
                pk=variant.pk,
            ).update(
                is_default=True,
                is_active=True,
                is_streamable=True,
            )

            count += 1

    modeladmin.message_user(
        request,
        f"{count} variant(s) set as default.",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Enable streaming for selected variants",
)
def enable_streaming(
    modeladmin,
    request,
    queryset,
):
    count = queryset.update(
        is_streamable=True,
        is_active=True,
    )

    modeladmin.message_user(
        request,
        f"Streaming enabled for {count} variant(s).",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Disable streaming for selected variants",
)
def disable_streaming(
    modeladmin,
    request,
    queryset,
):
    count = queryset.update(
        is_streamable=False,
        is_default=False,
    )

    modeladmin.message_user(
        request,
        f"Streaming disabled for {count} variant(s).",
        level=messages.WARNING,
    )


@admin.register(MusicTrackVariant)
class MusicTrackVariantAdmin(
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

    list_display_links = (
        "variant_type",
        "label",
    )

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

    autocomplete_fields = (
        "track",
    )

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

    ordering = (
        "-created_at",
        "-id",
    )

    fieldsets = (
        (
            "Track and variant",
            {
                "fields": (
                    "track",
                    (
                        "variant_type",
                        "label",
                        "locale",
                    ),
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
                    (
                        "duration_ms",
                        "source_start_ms",
                        "source_end_ms",
                    ),
                ),
            },
        ),
        (
            "Technical metadata",
            {
                "fields": (
                    (
                        "mime_type",
                        "codec",
                        "container",
                    ),
                    (
                        "bitrate_kbps",
                        "sample_rate_hz",
                        "channels",
                    ),
                    (
                        "file_size_bytes",
                        "checksum_sha256",
                    ),
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
                "classes": (
                    "collapse",
                ),
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

    @admin.display(
        description="Track",
        ordering="track__title",
    )
    def track_link(self, obj):
        return linked_object(
            obj.track,
        )

    @admin.display(
        description="Listen",
    )
    def audio_player(self, obj):
        return render_audio_player(
            obj.audio_file,
            width=230,
        )

    @admin.display(
        description="Audio preview",
    )
    def audio_player_large(self, obj):
        return render_audio_player(
            obj.audio_file,
            width=600,
        )

    @admin.display(
        description="Conversion",
    )
    def conversion_state(self, obj):
        return conversion_status_badge(obj)

    @admin.display(
        description="Latest job",
    )
    def conversion_job(self, obj):
        return render_conversion_job(obj)

    @admin.display(
        description="Media assets",
    )
    def media_assets_pretty(self, obj):
        return render_json(
            obj.media_assets
        )