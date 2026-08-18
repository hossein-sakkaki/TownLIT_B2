# apps/audio_catalog/admin/inlines.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-03.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from django.contrib import admin

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicRightsRecord,
    MusicTrackVariant,
    TrackContributor,
)

from .forms import (
    MusicArtworkInlineForm,
    MusicRightsRecordInlineForm,
    MusicTrackVariantInlineForm,
    SingleDefaultVariantFormSet,
    SinglePrimaryArtworkFormSet,
    TrackContributorInlineForm,
    TrackContributorInlineFormSet,
)
from .shared import (
    conversion_status_badge,
    render_audio_player,
    render_conversion_job,
    render_image_preview,
)


class MusicArtworkInline(admin.StackedInline):
    model = MusicArtwork
    form = MusicArtworkInlineForm
    formset = SinglePrimaryArtworkFormSet

    extra = 1
    max_num = 10
    show_change_link = True

    fieldsets = (
        (
            "Cover artwork",
            {
                "fields": (
                    "image",
                    "artwork_preview",
                    ("role", "label"),
                    ("is_primary", "is_active"),
                ),
            },
        ),
        (
            "Processing and advanced",
            {
                "classes": ("collapse",),
                "fields": (
                    "sort_order",
                    "conversion_state",
                    "conversion_job",
                ),
            },
        ),
    )

    readonly_fields = (
        "artwork_preview",
        "conversion_state",
        "conversion_job",
    )

    @admin.display(description="Preview")
    def artwork_preview(self, obj):
        return render_image_preview(
            getattr(obj, "image", None),
            width=180,
            height=180,
        )

    @admin.display(description="Conversion")
    def conversion_state(self, obj):
        if not obj or not obj.pk:
            return (
                "Save the track. Artwork conversion will "
                "start automatically."
            )

        return conversion_status_badge(obj)

    @admin.display(description="Latest job")
    def conversion_job(self, obj):
        return render_conversion_job(obj) if obj and obj.pk else "—"


class MusicTrackVariantInline(admin.StackedInline):
    model = MusicTrackVariant
    form = MusicTrackVariantInlineForm
    formset = SingleDefaultVariantFormSet

    extra = 1
    max_num = 30
    show_change_link = True

    fieldsets = (
        (
            "Playable audio",
            {
                "fields": (
                    "audio_file",
                    "audio_preview",
                    ("variant_type", "label", "locale"),
                    ("is_default", "is_streamable", "is_active"),
                ),
            },
        ),
        (
            "Advanced playback and technical metadata",
            {
                "classes": ("collapse",),
                "fields": (
                    ("is_downloadable", "sort_order"),
                    ("duration_ms", "source_start_ms", "source_end_ms"),
                    ("mime_type", "codec", "container"),
                    ("bitrate_kbps", "sample_rate_hz", "channels"),
                    ("file_size_bytes", "checksum_sha256"),
                    "waveform_file",
                    "conversion_state",
                    "conversion_job",
                ),
            },
        ),
    )

    readonly_fields = (
        "audio_preview",
        "duration_ms",
        "conversion_state",
        "conversion_job",
    )

    @admin.display(description="Audio preview")
    def audio_preview(self, obj):
        return render_audio_player(
            getattr(obj, "audio_file", None),
            width=520,
        )

    @admin.display(description="Conversion")
    def conversion_state(self, obj):
        if not obj or not obj.pk:
            return (
                "Save the track. Audio conversion will "
                "start automatically."
            )

        return conversion_status_badge(obj)

    @admin.display(description="Latest job")
    def conversion_job(self, obj):
        return render_conversion_job(obj) if obj and obj.pk else "—"


class TrackContributorInline(admin.StackedInline):
    """
    Connect tracks to canonical AudioContributor records.

    Existing contributors are shown directly in the normal select.
    New contributors are created through Django's related-object
    + button and therefore always live in AudioContributor.
    """

    model = TrackContributor
    form = TrackContributorInlineForm
    formset = TrackContributorInlineFormSet

    extra = 1
    max_num = 10
    show_change_link = True

    #
    # Deliberately DO NOT use autocomplete_fields here.
    #
    # Django's normal ForeignKey select displays the canonical
    # AudioContributor records directly. This removes the separate
    # async autocomplete dependency from the normal music workflow.
    #

    fieldsets = (
        (
            "Contributor credit",
            {
                "description": (
                    "Select an existing Audio Contributor. "
                    "If it does not exist yet, use the + button beside "
                    "Contributor to create it once in the canonical "
                    "Audio Contributors table."
                ),
                "fields": (
                    "contributor",
                    ("role", "credit_text"),
                ),
            },
        ),
        (
            "Advanced credit settings",
            {
                "classes": ("collapse",),
                "fields": (
                    ("share_basis_points", "sort_order"),
                ),
            },
        ),
    )


class MusicRightsRecordInline(admin.StackedInline):
    """
    Complete the main rights workflow directly from the track page.
    """

    model = MusicRightsRecord
    form = MusicRightsRecordInlineForm

    extra = 1
    max_num = 1
    can_delete = False
    show_change_link = True

    autocomplete_fields = (
        "master_owner",
        "composition_owner",
        "licensor",
    )

    readonly_fields = (
        "reviewed_by",
        "reviewed_at",
    )

    fieldsets = (
        (
            "License basics",
            {
                "fields": (
                    ("status", "license_type"),
                    "apply_townlit_usage_preset",
                    ("provider_name", "provider_plan"),
                    ("effective_from", "effective_until"),
                    "territory_mode",
                    "territory_codes",
                ),
            },
        ),
        (
            "Required TownLIT permissions",
            {
                "description": (
                    "These permissions are required by the current "
                    "TownLIT music/content workflow."
                ),
                "fields": (
                    (
                        "ugc_use_allowed",
                        "streaming_allowed",
                        "synchronization_allowed",
                    ),
                    (
                        "clipping_allowed",
                        "hosting_allowed",
                        "sublicensing_to_end_users_allowed",
                    ),
                ),
            },
        ),
        (
            "Additional permissions",
            {
                "classes": ("collapse",),
                "fields": (
                    ("commercial_use_allowed", "adaptation_allowed"),
                    (
                        "standalone_download_allowed",
                        "external_export_allowed",
                    ),
                    "perpetual_existing_content_allowed",
                ),
            },
        ),
        (
            "Ownership, provider records and source",
            {
                "classes": ("collapse",),
                "fields": (
                    "master_owner",
                    "composition_owner",
                    "licensor",
                    "provider_account_reference",
                    "generation_reference",
                    "generation_prompt_hash",
                    "agreement_reference",
                    "license_version",
                    "source_url",
                ),
            },
        ),
        (
            "Attribution and restrictions",
            {
                "classes": ("collapse",),
                "fields": (
                    "attribution_required",
                    "attribution_text",
                    "restrictions",
                    "notes",
                ),
            },
        ),
        (
            "Legal review",
            {
                "classes": ("collapse",),
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                ),
            },
        ),
    )