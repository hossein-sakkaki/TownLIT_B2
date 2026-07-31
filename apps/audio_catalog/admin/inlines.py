# apps/audio_catalog/admin/inlines.py

from __future__ import annotations

from django.contrib import admin

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicTrackVariant,
    TrackContributor,
)

from .shared import (
    conversion_status_badge,
    render_audio_player,
    render_conversion_job,
    render_image_preview,
)


class MusicArtworkInline(admin.StackedInline):
    """
    Manage track artwork from the track page.
    """

    model = MusicArtwork
    extra = 1
    max_num = 10
    show_change_link = True

    fields = (
        (
            "role",
            "label",
        ),
        "image",
        "artwork_preview",
        (
            "is_primary",
            "is_active",
            "sort_order",
        ),
        (
            "conversion_state",
            "conversion_job",
        ),
    )

    readonly_fields = (
        "artwork_preview",
        "conversion_state",
        "conversion_job",
    )

    @admin.display(
        description="Preview",
    )
    def artwork_preview(self, obj):
        return render_image_preview(
            getattr(
                obj,
                "image",
                None,
            ),
            width=160,
            height=160,
        )

    @admin.display(
        description="Conversion",
    )
    def conversion_state(self, obj):
        if not obj or not obj.pk:
            return "Saved artwork will be converted automatically."

        return conversion_status_badge(obj)

    @admin.display(
        description="Latest job",
    )
    def conversion_job(self, obj):
        if not obj or not obj.pk:
            return "—"

        return render_conversion_job(obj)


class MusicTrackVariantInline(admin.StackedInline):
    """
    Manage playable audio variants from the track page.
    """

    model = MusicTrackVariant
    extra = 1
    max_num = 30
    show_change_link = True

    fields = (
        (
            "variant_type",
            "label",
            "locale",
        ),
        "audio_file",
        "audio_preview",
        (
            "duration_ms",
            "source_start_ms",
            "source_end_ms",
        ),
        (
            "is_default",
            "is_streamable",
            "is_downloadable",
            "is_active",
        ),
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
        (
            "conversion_state",
            "conversion_job",
        ),
        "sort_order",
    )

    readonly_fields = (
        "audio_preview",
        "conversion_state",
        "conversion_job",
    )

    @admin.display(
        description="Audio preview",
    )
    def audio_preview(self, obj):
        return render_audio_player(
            getattr(
                obj,
                "audio_file",
                None,
            ),
            width=420,
        )

    @admin.display(
        description="Conversion",
    )
    def conversion_state(self, obj):
        if not obj or not obj.pk:
            return "Saved audio will be converted automatically."

        return conversion_status_badge(obj)

    @admin.display(
        description="Latest job",
    )
    def conversion_job(self, obj):
        if not obj or not obj.pk:
            return "—"

        return render_conversion_job(obj)


class TrackContributorInline(admin.TabularInline):
    """
    Manage track credits.
    """

    model = TrackContributor
    extra = 1
    show_change_link = True

    fields = (
        "contributor",
        "role",
        "credit_text",
        "share_basis_points",
        "sort_order",
    )

    autocomplete_fields = (
        "contributor",
    )