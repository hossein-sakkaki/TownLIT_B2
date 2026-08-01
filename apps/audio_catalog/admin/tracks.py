# apps/audio_catalog/admin/tracks.py

from __future__ import annotations

from django.contrib import admin, messages
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicRightsRecord,
    MusicTrack,
    MusicTrackVariant,
)
from apps.audio_catalog.services.publishing import (
    publish_track,
    suspend_track,
)

from .inlines import (
    MusicArtworkInline,
    MusicTrackVariantInline,
    TrackContributorInline,
)
from .shared import (
    LargeResultAdminMixin,
    linked_object,
    render_audio_player,
    render_image_preview,
    status_badge,
)


@admin.action(
    description="Publish selected tracks",
)
def publish_selected(
    modeladmin,
    request,
    queryset,
):
    """
    Publish only fully ready tracks.
    """

    succeeded = 0
    failures: list[str] = []

    for track in queryset.iterator():
        try:
            publish_track(
                track=track,
                actor=request.user,
            )
            succeeded += 1
        except Exception as exc:
            failures.append(
                f"{track.title}: {exc}"
            )

    if succeeded:
        modeladmin.message_user(
            request,
            f"{succeeded} track(s) published.",
            level=messages.SUCCESS,
        )

    if failures:
        modeladmin.message_user(
            request,
            " | ".join(failures[:15]),
            level=messages.ERROR,
        )


@admin.action(
    description="Move selected tracks to review",
)
def move_selected_to_review(
    modeladmin,
    request,
    queryset,
):
    """
    Move draft tracks into editorial review.
    """

    count = queryset.exclude(
        status=MusicTrack.Status.PUBLISHED,
    ).update(
        status=MusicTrack.Status.REVIEW,
        updated_by=request.user,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} track(s) moved to review.",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Suspend selected tracks",
)
def suspend_selected(
    modeladmin,
    request,
    queryset,
):
    """
    Suspend selected tracks safely.
    """

    succeeded = 0
    failures: list[str] = []

    for track in queryset.iterator():
        try:
            suspend_track(
                track=track,
                actor=request.user,
            )
            succeeded += 1
        except Exception as exc:
            failures.append(
                f"{track.title}: {exc}"
            )

    if succeeded:
        modeladmin.message_user(
            request,
            f"{succeeded} track(s) suspended.",
            level=messages.WARNING,
        )

    if failures:
        modeladmin.message_user(
            request,
            " | ".join(failures[:15]),
            level=messages.ERROR,
        )


@admin.action(
    description="Archive selected tracks",
)
def archive_selected(
    modeladmin,
    request,
    queryset,
):
    """
    Archive tracks without deleting them.
    """

    count = queryset.update(
        status=MusicTrack.Status.ARCHIVED,
        archived_at=timezone.now(),
        updated_by=request.user,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} track(s) archived.",
        level=messages.WARNING,
    )


@admin.action(
    description="Mark selected tracks as test assets",
)
def mark_as_test_asset(
    modeladmin,
    request,
    queryset,
):
    count = queryset.update(
        is_test_asset=True,
        updated_by=request.user,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} track(s) marked as test assets.",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Remove test-asset flag",
)
def remove_test_asset_flag(
    modeladmin,
    request,
    queryset,
):
    count = queryset.update(
        is_test_asset=False,
        updated_by=request.user,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} track(s) made available for normal publishing.",
        level=messages.SUCCESS,
    )


@admin.action(
    description="Rebuild search documents",
)
def rebuild_search_documents(
    modeladmin,
    request,
    queryset,
):
    """
    Rebuild normalized searchable text.
    """

    updated = 0

    for track in queryset.prefetch_related(
        "categories",
        "genres",
        "moods",
        "tags",
        "contributor_links__contributor",
    ).iterator():
        values = [
            track.title,
            track.subtitle,
            track.description,
            track.language_code,
            *track.categories.values_list(
                "name",
                flat=True,
            ),
            *track.genres.values_list(
                "name",
                flat=True,
            ),
            *track.moods.values_list(
                "name",
                flat=True,
            ),
            *track.tags.values_list(
                "name",
                flat=True,
            ),
            *track.contributor_links.values_list(
                "contributor__display_name",
                flat=True,
            ),
        ]

        document = " ".join(
            str(value).strip()
            for value in values
            if value and str(value).strip()
        )

        MusicTrack.objects.filter(
            pk=track.pk,
        ).update(
            search_document=document,
            updated_by=request.user,
            updated_at=timezone.now(),
        )

        updated += 1

    modeladmin.message_user(
        request,
        f"Search document rebuilt for {updated} track(s).",
        level=messages.SUCCESS,
    )


@admin.register(MusicTrack)
class MusicTrackAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    """
    Main operational music catalog admin.
    """

    list_display = (
        "track_artwork",
        "title_column",
        "catalog",
        "status_display",
        "readiness_display",
        "default_audio",
        "source_type",
        "is_instrumental",
        "is_ai_assisted",
        "is_test_asset",
        "published_at",
        "updated_at",
    )

    list_display_links = (
        "track_artwork",
        "title_column",
    )

    list_filter = (
        "status",
        "catalog",
        "source_type",
        "is_instrumental",
        "has_vocals",
        "is_ai_assisted",
        "is_explicit",
        "is_test_asset",
        "allow_ugc",
        "allow_streaming",
        "allow_external_export",
        "categories",
        "genres",
        "moods",
        "published_at",
    )

    search_fields = (
        "title",
        "slug",
        "subtitle",
        "search_document",
        "public_id",
        "contributor_links__contributor__display_name",
    )

    filter_horizontal = (
        "categories",
        "genres",
        "moods",
        "tags",
    )

    readonly_fields = (
        "public_id",
        "slug",
        "readiness_panel",
        "primary_artwork_preview",
        "default_audio_preview",
        "rights_link",
        "published_at",
        "suspended_at",
        "archived_at",
        "created_at",
        "updated_at",
    )

    actions = (
        publish_selected,
        move_selected_to_review,
        suspend_selected,
        archive_selected,
        mark_as_test_asset,
        remove_test_asset_flag,
        rebuild_search_documents,
    )

    inlines = (
        MusicArtworkInline,
        MusicTrackVariantInline,
        TrackContributorInline,
    )

    date_hierarchy = "created_at"

    ordering = (
        "-created_at",
        "-id",
    )

    list_select_related = (
        "catalog",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        (
            "Catalog readiness",
            {
                "fields": (
                    "readiness_panel",
                    "primary_artwork_preview",
                    "default_audio_preview",
                    "rights_link",
                ),
            },
        ),
        (
            "Identity",
            {
                "fields": (
                    "public_id",
                    "catalog",
                    "title",
                    "slug",
                    "subtitle",
                    "description",
                ),
            },
        ),
        (
            "Classification",
            {
                "fields": (
                    "categories",
                    "genres",
                    "moods",
                    "tags",
                    "language_code",
                ),
            },
        ),
        (
            "Music details",
            {
                "fields": (
                    (
                        "duration_ms",
                        "bpm",
                    ),
                    (
                        "musical_key",
                        "time_signature",
                    ),
                    (
                        "is_instrumental",
                        "has_vocals",
                        "is_explicit",
                        "is_ai_assisted",
                    ),
                ),
            },
        ),
        (
            "Usage policy",
            {
                "fields": (
                    "source_type",
                    (
                        "allow_ugc",
                        "allow_streaming",
                    ),
                    (
                        "allow_standalone_download",
                        "allow_external_export",
                    ),
                    "allow_commercial_accounts",
                    (
                        "min_clip_duration_ms",
                        "max_clip_duration_ms",
                    ),
                ),
            },
        ),
        (
            "Publishing",
            {
                "fields": (
                    (
                        "status",
                        "is_test_asset",
                    ),
                    (
                        "sort_order",
                        "popularity_score",
                        "version",
                    ),
                    "published_at",
                    "suspended_at",
                    "archived_at",
                ),
            },
        ),
        (
            "Search and metadata",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "search_document",
                    "metadata",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        ready_artwork = MusicArtwork.objects.filter(
            track_id=OuterRef("pk"),
            is_primary=True,
            is_active=True,
            is_converted=True,
        )

        ready_audio = MusicTrackVariant.objects.filter(
            track_id=OuterRef("pk"),
            is_default=True,
            is_active=True,
            is_streamable=True,
            is_converted=True,
        )

        cleared_rights = MusicRightsRecord.objects.filter(
            track_id=OuterRef("pk"),
            status=MusicRightsRecord.Status.CLEARED,
        )

        return (
            queryset
            .annotate(
                admin_has_ready_artwork=Exists(
                    ready_artwork
                ),
                admin_has_ready_audio=Exists(
                    ready_audio
                ),
                admin_has_cleared_rights=Exists(
                    cleared_rights
                ),
            )
            .prefetch_related(
                "artworks",
                "variants",
                "contributor_links__contributor",
            )
        )

    @admin.display(
        description="Artwork",
    )
    def track_artwork(self, obj):
        artwork = next(
            (
                item
                for item in obj.artworks.all()
                if item.is_primary
            ),
            None,
        )

        return render_image_preview(
            getattr(
                artwork,
                "image",
                None,
            ),
            width=52,
            height=52,
        )

    @admin.display(
        description="Track",
        ordering="title",
    )
    def title_column(self, obj):
        if obj.subtitle:
            return format_html(
                "<strong>{}</strong>"
                "<br>"
                "<small>{}</small>",
                obj.title,
                obj.subtitle,
            )

        return format_html(
            "<strong>{}</strong>",
            obj.title,
        )

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_display(self, obj):
        color_map = {
            MusicTrack.Status.DRAFT: "#666666",
            MusicTrack.Status.REVIEW: "#5c6ac4",
            MusicTrack.Status.PUBLISHED: "#18864b",
            MusicTrack.Status.SUSPENDED: "#c57a00",
            MusicTrack.Status.ARCHIVED: "#8b8b8b",
        }

        return status_badge(
            obj.get_status_display(),
            background=color_map.get(
                obj.status,
                "#666666",
            ),
        )

    @admin.display(
        description="Readiness",
    )
    def readiness_display(self, obj):
        artwork = bool(
            getattr(
                obj,
                "admin_has_ready_artwork",
                False,
            )
        )
        audio = bool(
            getattr(
                obj,
                "admin_has_ready_audio",
                False,
            )
        )
        rights = bool(
            getattr(
                obj,
                "admin_has_cleared_rights",
                False,
            )
        )

        if artwork and audio and rights:
            return status_badge(
                "Ready",
                background="#18864b",
            )

        missing = []

        if not artwork:
            missing.append("artwork")

        if not audio:
            missing.append("audio")

        if not rights:
            missing.append("rights")

        return status_badge(
            f"Missing: {', '.join(missing)}",
            background="#c0392b",
        )

    @admin.display(
        description="Default audio",
    )
    def default_audio(self, obj):
        variant = next(
            (
                item
                for item in obj.variants.all()
                if item.is_default
            ),
            None,
        )

        return render_audio_player(
            getattr(
                variant,
                "audio_file",
                None,
            ),
            width=230,
        )

    @admin.display(
        description="Primary artwork",
    )
    def primary_artwork_preview(self, obj):
        if not obj or not obj.pk:
            return "Save the track before adding artwork."

        artwork = (
            obj.artworks
            .filter(
                is_primary=True,
                is_active=True,
            )
            .order_by(
                "sort_order",
                "id",
            )
            .first()
        )

        if artwork is None:
            return "No primary artwork."

        return render_image_preview(
            artwork.image,
            width=260,
            height=260,
        )

    @admin.display(
        description="Default playback",
    )
    def default_audio_preview(self, obj):
        if not obj or not obj.pk:
            return "Save the track before adding audio."

        variant = (
            obj.variants
            .filter(
                is_default=True,
                is_active=True,
            )
            .order_by(
                "sort_order",
                "id",
            )
            .first()
        )

        if variant is None:
            return "No default playback variant."

        return render_audio_player(
            variant.audio_file,
            width=520,
        )

    @admin.display(
        description="Rights record",
    )
    def rights_link(self, obj):
        if not obj or not obj.pk:
            return "Save the track first."

        try:
            rights = obj.rights
        except MusicRightsRecord.DoesNotExist:
            add_url = (
                reverse(
                    "admin:audio_catalog_musicrightsrecord_add"
                )
                + f"?track={obj.pk}"
            )

            return format_html(
                '<a class="button" href="{}">'
                "Create rights record"
                "</a>",
                add_url,
            )

        return linked_object(
            rights,
            label=(
                f"{rights.get_status_display()} · "
                f"{rights.get_license_type_display()}"
            ),
        )

    @admin.display(
        description="Readiness details",
    )
    def readiness_panel(self, obj):
        if not obj or not obj.pk:
            return "Save the track to evaluate readiness."

        artwork_ready = obj.artworks.filter(
            is_primary=True,
            is_active=True,
            is_converted=True,
        ).exists()

        audio_ready = obj.variants.filter(
            is_default=True,
            is_active=True,
            is_streamable=True,
            is_converted=True,
        ).exists()

        try:
            rights = obj.rights
            rights_ready = (
                rights.status
                == MusicRightsRecord.Status.CLEARED
            )
        except MusicRightsRecord.DoesNotExist:
            rights_ready = False

        def item(
            label: str,
            ready: bool,
        ) -> str:
            icon = "✅" if ready else "❌"

            return (
                f"<li style='margin:5px 0;'>"
                f"{icon} {label}"
                f"</li>"
            )

        return format_html(
            (
                '<div style="'
                'padding:12px 16px;'
                'border:1px solid #d8d8d8;'
                'border-radius:10px;'
                'background:#fafafa;'
                '">'
                "<strong>Publishing requirements</strong>"
                '<ul style="margin:8px 0 0 18px;">'
                "{}{}{}"
                "</ul>"
                "</div>"
            ),
            format_html(
                item(
                    "Primary artwork is converted",
                    artwork_ready,
                )
            ),
            format_html(
                item(
                    "Default audio is converted",
                    audio_ready,
                )
            ),
            format_html(
                item(
                    "Rights are cleared",
                    rights_ready,
                )
            ),
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.created_by_id:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )