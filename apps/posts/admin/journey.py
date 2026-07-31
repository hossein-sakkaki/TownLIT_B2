# apps/posts/admin/journey.py

import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.posts.admin.common import admin_change_link_for_instance
from apps.posts.constants.journeys import (
    JOURNEY_ACTIVE_DURATION_HOURS,
    JOURNEY_MAX_ENTRIES_PER_DAY,
    JourneyRetentionPolicy,
)
from apps.posts.models.journey import (
    Journey,
    JourneyEntry,
    JourneyEntryView,
)


# ============================================================
# Shared helpers
# ============================================================

def csv_safe_value(value):
    """
    Prevent spreadsheet formula injection in exported CSV files.
    """
    if value is None:
        return ""

    text = str(value)

    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"

    return text


def generic_owner_admin_link(content_type, object_id):
    """
    Build an admin link for a generic owner.
    """
    if content_type is None or object_id is None:
        return "-"

    fallback = (
        f"{content_type.app_label}."
        f"{content_type.model} #{object_id}"
    )

    try:
        model_class = content_type.model_class()

        if model_class is None:
            return fallback

        owner = model_class._default_manager.filter(
            pk=object_id,
        ).first()

        if owner is None:
            return fallback

        return admin_change_link_for_instance(owner)
    except Exception:
        return fallback


# ============================================================
# Filters
# ============================================================

class JourneyCloseStatusFilter(SimpleListFilter):
    """
    Filter Journeys by their close state.
    """

    title = "Close status"
    parameter_name = "journey_close_status"

    def lookups(self, request, model_admin):
        return (
            ("open", "Open"),
            ("closed", "Closed"),
            ("closed_private", "Closed privately"),
            ("closed_public", "Closed publicly"),
        )

    def queryset(self, request, queryset):
        value = self.value()

        if value == "open":
            return queryset.filter(closed_at__isnull=True)

        if value == "closed":
            return queryset.filter(closed_at__isnull=False)

        if value == "closed_private":
            return queryset.filter(
                closed_at__isnull=False,
                close_is_private=True,
            )

        if value == "closed_public":
            return queryset.filter(
                closed_at__isnull=False,
                close_is_private=False,
            )

        return queryset


class JourneyCapacityFilter(SimpleListFilter):
    """
    Filter Journeys based on their active entry capacity.
    """

    title = "Entry capacity"
    parameter_name = "journey_capacity"

    def lookups(self, request, model_admin):
        return (
            ("empty", "Empty"),
            ("available", "Has available capacity"),
            ("full", "Full"),
        )

    def queryset(self, request, queryset):
        value = self.value()

        if not value:
            return queryset

        queryset = queryset.annotate(
            filter_active_entry_count=Count(
                "entries",
                filter=Q(entries__is_active=True),
                distinct=True,
            )
        )

        if value == "empty":
            return queryset.filter(filter_active_entry_count=0)

        if value == "available":
            return queryset.filter(
                filter_active_entry_count__gt=0,
                filter_active_entry_count__lt=JOURNEY_MAX_ENTRIES_PER_DAY,
            )

        if value == "full":
            return queryset.filter(
                filter_active_entry_count__gte=JOURNEY_MAX_ENTRIES_PER_DAY,
            )

        return queryset


class JourneyEntryLifecycleFilter(SimpleListFilter):
    """
    Filter Journey entries by lifecycle state.
    """

    title = "Lifecycle"
    parameter_name = "journey_entry_lifecycle"

    def lookups(self, request, model_admin):
        return (
            ("live", "Live"),
            ("scheduled", "Scheduled"),
            ("expired", "Expired"),
            ("archived", "Archived"),
            ("unavailable", "Unavailable"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        now = timezone.now()

        if value == "live":
            return queryset.filter(
                is_active=True,
                is_hidden=False,
                is_suspended=False,
                archived_at__isnull=True,
                published_at__lte=now,
                expires_at__gt=now,
            ).exclude(
                rendered_image=""
            ).exclude(
                thumbnail=""
            )

        if value == "scheduled":
            return queryset.filter(
                archived_at__isnull=True,
                published_at__gt=now,
            )

        if value == "expired":
            return queryset.filter(
                archived_at__isnull=True,
                expires_at__lte=now,
            )

        if value == "archived":
            return queryset.filter(
                archived_at__isnull=False,
            )

        if value == "unavailable":
            return queryset.filter(
                Q(is_active=False)
                | Q(is_hidden=True)
                | Q(is_suspended=True)
                | Q(rendered_image="")
                | Q(thumbnail="")
            )

        return queryset


class JourneyEntryMusicFilter(SimpleListFilter):
    """
    Filter Journey entries based on music availability.
    """

    title = "Music"
    parameter_name = "journey_entry_music"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has music"),
            ("no", "No music"),
            ("incomplete", "Incomplete music data"),
        )

    def queryset(self, request, queryset):
        value = self.value()

        complete_music = (
            Q(music_track__isnull=False)
            & Q(music_variant__isnull=False)
            & Q(music_clip_start_ms__isnull=False)
            & Q(music_clip_end_ms__isnull=False)
        )

        any_music_data = (
            Q(music_track__isnull=False)
            | Q(music_variant__isnull=False)
            | Q(music_clip_start_ms__isnull=False)
            | Q(music_clip_end_ms__isnull=False)
        )

        if value == "yes":
            return queryset.filter(complete_music)

        if value == "no":
            return queryset.exclude(any_music_data)

        if value == "incomplete":
            return queryset.filter(any_music_data).exclude(
                complete_music
            )

        return queryset


# ============================================================
# Journey Entry Inline
# ============================================================

class JourneyEntryInline(admin.TabularInline):
    """
    Read-only entry overview inside a Journey.
    """

    model = JourneyEntry
    extra = 0
    can_delete = False
    show_change_link = True

    fields = (
        "sequence",
        "entry_link",
        "thumbnail_preview",
        "lifecycle_badge",
        "visibility",
        "is_active",
        "has_music_badge",
        "published_at",
        "expires_at",
    )

    readonly_fields = fields
    ordering = ("sequence", "id")

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "journey",
                "content_type",
                "music_track",
                "music_variant",
            )
        )

    @admin.display(description="Entry")
    def entry_link(self, obj):
        if obj is None or obj.pk is None:
            return "-"

        try:
            url = reverse(
                "admin:posts_journeyentry_change",
                args=[obj.pk],
            )
        except Exception:
            return str(obj)

        return format_html(
            '<a href="{}">Entry #{}</a>',
            url,
            obj.pk,
        )

    @admin.display(description="Thumbnail")
    def thumbnail_preview(self, obj):
        if not obj or not obj.thumbnail:
            return "—"

        try:
            return format_html(
                '<img src="{}" alt="Journey thumbnail" '
                'style="width:72px;height:72px;object-fit:cover;'
                'border-radius:8px;border:1px solid #ddd;">',
                obj.thumbnail.url,
            )
        except Exception:
            return "Unavailable"

    @admin.display(description="Lifecycle")
    def lifecycle_badge(self, obj):
        return JourneyEntryAdmin.render_lifecycle_badge(obj)

    @admin.display(description="Music", boolean=True)
    def has_music_badge(self, obj):
        return obj.has_music


# ============================================================
# Journey Admin
# ============================================================

@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    """
    Admin for one owner-local-day Journey chapter.
    """

    list_display = (
        "id",
        "owner_link",
        "local_date",
        "timezone_name",
        "palette_mode",
        "active_entry_count",
        "remaining_capacity_display",
        "close_status_badge",
        "created_at",
        "updated_at",
    )

    list_filter = (
        JourneyCloseStatusFilter,
        JourneyCapacityFilter,
        "palette_mode",
        "local_date",
        "created_at",
    )

    search_fields = (
        "id",
        "slug",
        "object_id",
        "timezone_name",
        "close_text",
    )

    date_hierarchy = "local_date"
    ordering = ("-local_date", "-id")
    list_per_page = 50
    list_select_related = ("content_type",)

    readonly_fields = (
        "id",
        "slug",
        "owner_link",
        "active_entry_count",
        "total_entry_count",
        "remaining_capacity_display",
        "created_at",
        "updated_at",
    )

    raw_id_fields = ("content_type",)
    inlines = (JourneyEntryInline,)

    fieldsets = (
        (
            "Journey identity",
            {
                "fields": (
                    ("id", "slug"),
                    ("local_date", "timezone_name"),
                    ("palette_mode", "display_seed"),
                ),
            },
        ),
        (
            "Owner",
            {
                "fields": (
                    ("content_type", "object_id"),
                    "owner_link",
                ),
            },
        ),
        (
            "Journey Close",
            {
                "fields": (
                    "close_text",
                    ("close_is_private", "closed_at"),
                ),
            },
        ),
        (
            "Capacity",
            {
                "fields": (
                    (
                        "active_entry_count",
                        "total_entry_count",
                        "remaining_capacity_display",
                    ),
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    ("created_at", "updated_at"),
                ),
            },
        ),
    )

    actions = (
        "action_make_close_private",
        "action_make_close_public",
        "action_reopen_journeys",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        return queryset.annotate(
            admin_active_entry_count=Count(
                "entries",
                filter=Q(entries__is_active=True),
                distinct=True,
            ),
            admin_total_entry_count=Count(
                "entries",
                distinct=True,
            ),
        )

    @admin.display(description="Owner")
    def owner_link(self, obj):
        return generic_owner_admin_link(
            getattr(obj, "content_type", None),
            getattr(obj, "object_id", None),
        )

    @admin.display(
        description="Active entries",
        ordering="admin_active_entry_count",
    )
    def active_entry_count(self, obj):
        annotated_count = getattr(
            obj,
            "admin_active_entry_count",
            None,
        )

        if annotated_count is not None:
            return annotated_count

        return obj.entries.filter(is_active=True).count()

    @admin.display(
        description="Total entries",
        ordering="admin_total_entry_count",
    )
    def total_entry_count(self, obj):
        annotated_count = getattr(
            obj,
            "admin_total_entry_count",
            None,
        )

        if annotated_count is not None:
            return annotated_count

        return obj.entries.count()

    @admin.display(description="Remaining capacity")
    def remaining_capacity_display(self, obj):
        count = getattr(
            obj,
            "admin_active_entry_count",
            None,
        )

        if count is None:
            count = obj.entries.filter(is_active=True).count()

        remaining = max(
            JOURNEY_MAX_ENTRIES_PER_DAY - count,
            0,
        )

        return f"{remaining} / {JOURNEY_MAX_ENTRIES_PER_DAY}"

    @admin.display(description="Close status")
    def close_status_badge(self, obj):
        if obj.closed_at is None:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:12px;background:#7f8c8d;color:#fff;">'
                "OPEN"
                "</span>"
            )

        if obj.close_is_private:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:12px;background:#8e44ad;color:#fff;">'
                "CLOSED · PRIVATE"
                "</span>"
            )

        return format_html(
            '<span style="display:inline-block;padding:3px 8px;'
            'border-radius:12px;background:#27ae60;color:#fff;">'
            "CLOSED · PUBLIC"
            "</span>"
        )

    @admin.action(description="Make selected Journey Close texts private")
    def action_make_close_private(self, request, queryset):
        closed_journeys = queryset.filter(
            closed_at__isnull=False,
        )

        updated = closed_journeys.update(
            close_is_private=True,
            updated_at=timezone.now(),
        )

        skipped = queryset.count() - updated

        self.message_user(
            request,
            (
                f"{updated} Journey Close record(s) made private. "
                f"{skipped} open Journey(s) skipped."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(description="Make selected Journey Close texts public")
    def action_make_close_public(self, request, queryset):
        closed_journeys = queryset.filter(
            closed_at__isnull=False,
        ).exclude(
            close_text=""
        )

        updated = closed_journeys.update(
            close_is_private=False,
            updated_at=timezone.now(),
        )

        skipped = queryset.count() - updated

        self.message_user(
            request,
            (
                f"{updated} Journey Close record(s) made public. "
                f"{skipped} open or empty Journey(s) skipped."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Reopen selected Journeys and clear Journey Close"
    )
    def action_reopen_journeys(self, request, queryset):
        closed_journeys = queryset.filter(
            closed_at__isnull=False,
        )

        updated = closed_journeys.update(
            close_text="",
            close_is_private=True,
            closed_at=None,
            updated_at=timezone.now(),
        )

        skipped = queryset.count() - updated

        self.message_user(
            request,
            (
                f"{updated} Journey(s) reopened and their Close text cleared. "
                f"{skipped} already-open Journey(s) skipped."
            ),
            level=messages.WARNING,
        )


# ============================================================
# Journey Entry Admin
# ============================================================

@admin.register(JourneyEntry)
class JourneyEntryAdmin(admin.ModelAdmin):
    """
    Admin for immutable published Journey entries.

    Published composition, media, sequence, owner, and music snapshots are
    read-only. Moderation and lifecycle state remain administratively
    manageable.
    """

    list_display = (
        "id",
        "journey_link",
        "sequence",
        "owner_link",
        "thumbnail_preview",
        "lifecycle_badge",
        "visibility",
        "is_active",
        "is_hidden",
        "is_suspended",
        "has_music_badge",
        "retention_policy",
        "view_count_internal",
        "unique_viewers_count",
        "reactions_count",
        "published_at",
    )

    list_filter = (
        JourneyEntryLifecycleFilter,
        JourneyEntryMusicFilter,
        "visibility",
        "is_active",
        "is_hidden",
        "is_suspended",
        "retention_policy",
        "media_type",
        "visual_source_type",
        "published_at",
        "expires_at",
    )

    search_fields = (
        "id",
        "slug",
        "journey__id",
        "journey__slug",
        "object_id",
        "composition_public_id_snapshot",
        "render_job_public_id_snapshot",
        "composition_document_sha256",
        "music_attribution_text",
    )

    ordering = (
        "-published_at",
        "-id",
    )

    date_hierarchy = "published_at"
    list_per_page = 50

    list_select_related = (
        "journey",
        "content_type",
        "composition",
        "render_job",
        "music_track",
        "music_variant",
    )

    raw_id_fields = (
        "journey",
        "content_type",
        "composition",
        "render_job",
        "music_track",
        "music_variant",
    )

    readonly_fields = (
        "id",
        "slug",
        "journey_link",
        "owner_link",
        "lifecycle_badge",
        "is_live_display",
        "is_archived_display",
        "rendered_image_preview",
        "thumbnail_preview_large",
        "composition_link",
        "render_job_link",
        "composition_public_id_snapshot",
        "render_job_public_id_snapshot",
        "composition_revision",
        "composition_document_sha256",
        "rendered_image",
        "thumbnail",
        "published_at",
        "expires_at",
        "archived_at",
        "view_count_internal",
        "unique_viewers_count",
        "reactions_count",
        "reactions_breakdown",
        "last_viewed_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    ("id", "slug"),
                    ("journey", "journey_link"),
                    ("sequence", "media_type", "visual_source_type"),
                ),
            },
        ),
        (
            "Owner snapshot",
            {
                "fields": (
                    ("content_type", "object_id"),
                    "owner_link",
                ),
            },
        ),
        (
            "Published assets",
            {
                "fields": (
                    "rendered_image_preview",
                    "thumbnail_preview_large",
                    "rendered_image",
                    "thumbnail",
                ),
            },
        ),
        (
            "Creative Editor audit",
            {
                "fields": (
                    ("composition", "composition_link"),
                    ("render_job", "render_job_link"),
                    "composition_public_id_snapshot",
                    "render_job_public_id_snapshot",
                    "composition_revision",
                    "composition_document_sha256",
                ),
            },
        ),
        (
            "Music snapshot",
            {
                "fields": (
                    ("music_track", "music_variant"),
                    (
                        "music_clip_start_ms",
                        "music_clip_end_ms",
                        "display_duration_ms",
                    ),
                    "music_volume",
                    "music_attribution_text",
                ),
            },
        ),
        (
            "Visibility and moderation",
            {
                "fields": (
                    (
                        "visibility",
                        "is_active",
                        "is_hidden",
                        "is_suspended",
                    ),
                ),
            },
        ),
        (
            "Retention lifecycle",
            {
                "fields": (
                    "retention_policy",
                    ("published_at", "expires_at", "archived_at"),
                    (
                        "lifecycle_badge",
                        "is_live_display",
                        "is_archived_display",
                    ),
                ),
            },
        ),
        (
            "Interactions and analytics",
            {
                "fields": (
                    "view_count_internal",
                    "unique_viewers_count",
                    "reactions_count",
                    "reactions_breakdown",
                    "last_viewed_at",
                ),
            },
        ),
        (
            "System",
            {
                "fields": (
                    "updated_at",
                ),
            },
        ),
    )

    actions = (
        "action_activate_entries",
        "action_deactivate_entries",
        "action_hide_entries",
        "action_unhide_entries",
        "action_archive_entries",
        "action_restore_archived_entries",
        "action_set_retention_keep",
        "action_recalculate_view_analytics",
    )

    @admin.display(description="Journey")
    def journey_link(self, obj):
        journey = getattr(obj, "journey", None)

        if journey is None:
            return "-"

        return admin_change_link_for_instance(journey)

    @admin.display(description="Owner")
    def owner_link(self, obj):
        return generic_owner_admin_link(
            getattr(obj, "content_type", None),
            getattr(obj, "object_id", None),
        )

    @admin.display(description="Thumbnail")
    def thumbnail_preview(self, obj):
        if not obj.thumbnail:
            return "—"

        try:
            return format_html(
                '<img src="{}" alt="Journey thumbnail" '
                'style="width:58px;height:58px;object-fit:cover;'
                'border-radius:7px;border:1px solid #ddd;">',
                obj.thumbnail.url,
            )
        except Exception:
            return "Unavailable"

    @admin.display(description="Rendered image preview")
    def rendered_image_preview(self, obj):
        if not obj.rendered_image:
            return format_html("<em>No rendered image</em>")

        try:
            return format_html(
                '<div style="margin-bottom:8px;">'
                '<a href="{}" target="_blank" rel="noopener">'
                '<img src="{}" alt="Rendered Journey image" '
                'style="max-width:420px;max-height:620px;'
                'object-fit:contain;border-radius:10px;'
                'border:1px solid #ddd;background:#fafafa;">'
                "</a>"
                "</div>",
                obj.rendered_image.url,
                obj.rendered_image.url,
            )
        except Exception:
            return format_html(
                "<em>Rendered image URL is unavailable.</em>"
            )

    @admin.display(description="Thumbnail preview")
    def thumbnail_preview_large(self, obj):
        if not obj.thumbnail:
            return format_html("<em>No thumbnail</em>")

        try:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">'
                '<img src="{}" alt="Journey thumbnail" '
                'style="max-width:220px;max-height:220px;'
                'object-fit:cover;border-radius:10px;'
                'border:1px solid #ddd;">'
                "</a>",
                obj.thumbnail.url,
                obj.thumbnail.url,
            )
        except Exception:
            return format_html(
                "<em>Thumbnail URL is unavailable.</em>"
            )

    @admin.display(description="Composition")
    def composition_link(self, obj):
        composition = getattr(obj, "composition", None)
        return admin_change_link_for_instance(composition)

    @admin.display(description="Render job")
    def render_job_link(self, obj):
        render_job = getattr(obj, "render_job", None)
        return admin_change_link_for_instance(render_job)

    @staticmethod
    def render_lifecycle_badge(obj):
        now = timezone.now()

        if obj.archived_at is not None:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:12px;background:#34495e;color:#fff;">'
                "ARCHIVED"
                "</span>"
            )

        if not obj.is_active or obj.is_hidden or obj.is_suspended:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:12px;background:#c0392b;color:#fff;">'
                "UNAVAILABLE"
                "</span>"
            )

        if obj.published_at > now:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:12px;background:#2980b9;color:#fff;">'
                "SCHEDULED"
                "</span>"
            )

        if obj.expires_at <= now:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:12px;background:#d35400;color:#fff;">'
                "EXPIRED"
                "</span>"
            )

        return format_html(
            '<span style="display:inline-block;padding:3px 8px;'
            'border-radius:12px;background:#27ae60;color:#fff;">'
            "LIVE"
            "</span>"
        )

    @admin.display(description="Lifecycle")
    def lifecycle_badge(self, obj):
        return self.render_lifecycle_badge(obj)

    @admin.display(description="Live", boolean=True)
    def is_live_display(self, obj):
        return obj.is_live

    @admin.display(description="Archived", boolean=True)
    def is_archived_display(self, obj):
        return obj.is_archived

    @admin.display(description="Music", boolean=True)
    def has_music_badge(self, obj):
        return obj.has_music

    @admin.action(description="Activate selected Journey entries")
    def action_activate_entries(self, request, queryset):
        updated = queryset.update(
            is_active=True,
            updated_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} Journey entry/entries activated.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected Journey entries")
    def action_deactivate_entries(self, request, queryset):
        updated = queryset.update(
            is_active=False,
            updated_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} Journey entry/entries deactivated.",
            level=messages.WARNING,
        )

    @admin.action(description="Hide selected Journey entries")
    def action_hide_entries(self, request, queryset):
        updated = queryset.update(
            is_hidden=True,
            updated_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} Journey entry/entries hidden.",
            level=messages.WARNING,
        )

    @admin.action(description="Unhide selected Journey entries")
    def action_unhide_entries(self, request, queryset):
        updated = queryset.update(
            is_hidden=False,
            updated_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} Journey entry/entries unhidden.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Archive selected Journey entries")
    def action_archive_entries(self, request, queryset):
        now = timezone.now()

        updated = queryset.filter(
            archived_at__isnull=True,
        ).update(
            archived_at=now,
            updated_at=now,
        )

        skipped = queryset.count() - updated

        self.message_user(
            request,
            (
                f"{updated} Journey entry/entries archived. "
                f"{skipped} already archived."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(description="Restore selected archived Journey entries")
    def action_restore_archived_entries(self, request, queryset):
        now = timezone.now()

        restored = queryset.filter(
            archived_at__isnull=False,
        ).update(
            archived_at=None,
            updated_at=now,
        )

        expired_after_restore = queryset.filter(
            archived_at__isnull=True,
            expires_at__lte=now,
        ).count()

        self.message_user(
            request,
            (
                f"{restored} Journey entry/entries restored from archive. "
                f"{expired_after_restore} selected entry/entries are expired "
                "and will not become live until their lifecycle is changed."
            ),
            level=(
                messages.WARNING
                if expired_after_restore
                else messages.SUCCESS
            ),
        )

    @admin.action(description="Set selected retention policy to KEEP")
    def action_set_retention_keep(self, request, queryset):
        updated = queryset.update(
            retention_policy=JourneyRetentionPolicy.KEEP,
            updated_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} Journey entry/entries set to KEEP.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Recalculate view analytics from viewer records"
    )
    def action_recalculate_view_analytics(self, request, queryset):
        recalculated = 0

        for entry in queryset.iterator():
            aggregates = entry.viewer_records.aggregate(
                total_views=Sum("view_count"),
                unique_viewers=Count("viewer_id", distinct=True),
                latest_view=Max("last_viewed_at"),
            )

            total_views = aggregates["total_views"] or 0
            unique_viewers = aggregates["unique_viewers"] or 0
            latest_view = aggregates["latest_view"]

            type(entry).objects.filter(pk=entry.pk).update(
                view_count_internal=total_views,
                unique_viewers_count=unique_viewers,
                last_viewed_at=latest_view,
                updated_at=timezone.now(),
            )

            recalculated += 1

        self.message_user(
            request,
            (
                f"View analytics recalculated for "
                f"{recalculated} Journey entry/entries."
            ),
            level=messages.SUCCESS,
        )


# ============================================================
# Journey Entry View Admin
# ============================================================

@admin.register(JourneyEntryView)
class JourneyEntryViewAdmin(admin.ModelAdmin):
    """
    Read-only analytics panel for private Journey viewer records.
    """

    list_display = (
        "id",
        "entry_link",
        "viewer_link",
        "source",
        "view_count",
        "progress_display",
        "completed",
        "first_viewed_at",
        "last_viewed_at",
    )

    list_filter = (
        "completed",
        "source",
        "first_viewed_at",
        "last_viewed_at",
    )

    search_fields = (
        "id",
        "entry__id",
        "entry__slug",
        "viewer__username",
        "viewer__email",
        "viewer__name",
        "viewer__family",
    )

    ordering = (
        "-last_viewed_at",
        "-id",
    )

    date_hierarchy = "last_viewed_at"
    list_per_page = 100

    list_select_related = (
        "entry",
        "entry__journey",
        "viewer",
    )

    raw_id_fields = (
        "entry",
        "viewer",
    )

    readonly_fields = (
        "id",
        "entry_link",
        "viewer_link",
        "entry",
        "viewer",
        "first_viewed_at",
        "last_viewed_at",
        "view_count",
        "max_progress_ms",
        "progress_display",
        "completed",
        "source",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Viewer record",
            {
                "fields": (
                    "id",
                    ("entry", "entry_link"),
                    ("viewer", "viewer_link"),
                    ("source", "completed"),
                ),
            },
        ),
        (
            "Engagement",
            {
                "fields": (
                    "view_count",
                    ("max_progress_ms", "progress_display"),
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    ("first_viewed_at", "last_viewed_at"),
                    ("created_at", "updated_at"),
                ),
            },
        ),
    )

    actions = (
        "export_selected_views_csv",
        "recalculate_selected_entry_analytics",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Entry")
    def entry_link(self, obj):
        entry = getattr(obj, "entry", None)

        if entry is None:
            return "-"

        return admin_change_link_for_instance(entry)

    @admin.display(description="Viewer")
    def viewer_link(self, obj):
        viewer = getattr(obj, "viewer", None)

        if viewer is None:
            return "-"

        return admin_change_link_for_instance(viewer)

    @admin.display(description="Progress")
    def progress_display(self, obj):
        duration = getattr(
            getattr(obj, "entry", None),
            "display_duration_ms",
            0,
        ) or 0

        progress = obj.max_progress_ms or 0

        if duration <= 0:
            return f"{progress:,} ms"

        percentage = min(
            max((progress / duration) * 100, 0),
            100,
        )

        return (
            f"{progress:,} / {duration:,} ms "
            f"({percentage:.1f}%)"
        )

    @admin.action(description="Export selected viewer records as CSV")
    def export_selected_views_csv(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers can export Journey viewer analytics.",
                level=messages.ERROR,
            )
            return None

        response = HttpResponse(
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            'attachment; filename="journey-entry-views.csv"'
        )

        # UTF-8 BOM improves compatibility with spreadsheet applications.
        response.write("\ufeff")

        writer = csv.writer(response)

        writer.writerow(
            [
                "id",
                "entry_id",
                "journey_id",
                "viewer_id",
                "viewer_username",
                "viewer_email",
                "source",
                "view_count",
                "max_progress_ms",
                "completed",
                "first_viewed_at",
                "last_viewed_at",
                "created_at",
                "updated_at",
            ]
        )

        records = queryset.select_related(
            "entry",
            "entry__journey",
            "viewer",
        )

        for record in records.iterator():
            writer.writerow(
                [
                    record.id,
                    record.entry_id,
                    record.entry.journey_id,
                    record.viewer_id,
                    csv_safe_value(
                        getattr(record.viewer, "username", "")
                    ),
                    csv_safe_value(
                        getattr(record.viewer, "email", "")
                    ),
                    csv_safe_value(record.source),
                    record.view_count,
                    record.max_progress_ms,
                    record.completed,
                    (
                        record.first_viewed_at.isoformat()
                        if record.first_viewed_at
                        else ""
                    ),
                    (
                        record.last_viewed_at.isoformat()
                        if record.last_viewed_at
                        else ""
                    ),
                    (
                        record.created_at.isoformat()
                        if record.created_at
                        else ""
                    ),
                    (
                        record.updated_at.isoformat()
                        if record.updated_at
                        else ""
                    ),
                ]
            )

        return response

    @admin.action(
        description="Recalculate analytics for related Journey entries"
    )
    def recalculate_selected_entry_analytics(
        self,
        request,
        queryset,
    ):
        entry_ids = list(
            queryset.values_list(
                "entry_id",
                flat=True,
            ).distinct()
        )

        recalculated = 0

        for entry in JourneyEntry.objects.filter(
            pk__in=entry_ids,
        ).iterator():
            aggregates = entry.viewer_records.aggregate(
                total_views=Sum("view_count"),
                unique_viewers=Count("viewer_id", distinct=True),
                latest_view=Max("last_viewed_at"),
            )

            JourneyEntry.objects.filter(pk=entry.pk).update(
                view_count_internal=aggregates["total_views"] or 0,
                unique_viewers_count=aggregates["unique_viewers"] or 0,
                last_viewed_at=aggregates["latest_view"],
                updated_at=timezone.now(),
            )

            recalculated += 1

        self.message_user(
            request,
            (
                f"Analytics recalculated for "
                f"{recalculated} related Journey entry/entries."
            ),
            level=messages.SUCCESS,
        )