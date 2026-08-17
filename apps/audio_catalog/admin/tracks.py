# apps/audio_catalog/admin/tracks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-03.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from apps.audio_catalog.models import (
    MusicRightsRecord,
    MusicTrack,
)
from apps.audio_catalog.services.publishing import (
    publish_track,
    suspend_track,
)

from .forms import MusicTrackAdminForm
from .inlines import (
    MusicArtworkInline,
    MusicRightsRecordInline,
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


@dataclass(frozen=True)
class ReadinessCheck:
    label: str
    ready: bool
    detail: str = ""


@dataclass(frozen=True)
class TrackReadiness:
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return all(item.ready for item in self.checks)

    @property
    def missing_count(self) -> int:
        return sum(1 for item in self.checks if not item.ready)


def evaluate_track_readiness(track: MusicTrack) -> TrackReadiness:
    """
    Explain whether a Draft/Review track satisfies the requirements
    used by the current publishing service.
    """

    now = timezone.now()
    artworks = list(track.artworks.all())
    variants = list(track.variants.all())

    artwork_ready = any(
        item.is_primary and item.is_active and item.is_converted
        for item in artworks
    )

    audio_ready = any(
        item.is_default
        and item.is_active
        and item.is_converted
        and item.is_streamable
        for item in variants
    )

    try:
        rights = track.rights
    except MusicRightsRecord.DoesNotExist:
        rights = None

    rights_cleared = bool(
        rights and rights.status == MusicRightsRecord.Status.CLEARED
    )

    rights_dates_valid = bool(
        rights
        and (not rights.effective_from or rights.effective_from <= now)
        and (not rights.effective_until or rights.effective_until > now)
    )

    required_rights = (
        ("UGC", "ugc_use_allowed"),
        ("Streaming", "streaming_allowed"),
        ("Synchronization", "synchronization_allowed"),
        ("Clipping", "clipping_allowed"),
        ("Hosting", "hosting_allowed"),
        ("End-user sublicensing", "sublicensing_to_end_users_allowed"),
    )

    missing_rights = []

    if rights is not None:
        missing_rights = [
            label
            for label, field_name in required_rights
            if not getattr(rights, field_name, False)
        ]

    rights_matrix_ready = bool(rights and not missing_rights)

    # Current publish_track() calls can_use_track() without a country.
    # Therefore an ALLOW_LIST record cannot pass the current publish path.
    territory_ready = bool(
        rights
        and rights.territory_mode
        != MusicRightsRecord.TerritoryMode.ALLOW_LIST
    )

    territory_detail = ""

    if (
        rights
        and rights.territory_mode
        == MusicRightsRecord.TerritoryMode.ALLOW_LIST
    ):
        territory_detail = (
            "The current publishing service has no country context "
            "for an Allow List license."
        )

    checks = (
        ReadinessCheck(
            "Catalog is active",
            bool(track.catalog and track.catalog.is_active),
            "The selected catalog must be active.",
        ),
        ReadinessCheck(
            "Track is a normal catalog asset",
            not track.is_test_asset,
            (
                "Remove the test-asset flag before publishing."
                if track.is_test_asset
                else ""
            ),
        ),
        ReadinessCheck(
            "Track usage policy allows TownLIT content",
            bool(track.allow_ugc and track.allow_streaming),
            "Allow UGC and Allow streaming must both be enabled.",
        ),
        ReadinessCheck(
            "Primary artwork is converted",
            artwork_ready,
            (
                ""
                if artwork_ready
                else "Upload a cover image and wait until conversion is Ready."
            ),
        ),
        ReadinessCheck(
            "Default audio is converted",
            audio_ready,
            (
                ""
                if audio_ready
                else "Upload playable audio and wait until conversion is Ready."
            ),
        ),
        ReadinessCheck(
            "Rights record exists and is cleared",
            rights_cleared,
            (
                ""
                if rights_cleared
                else (
                    "Complete the Rights section and mark it Cleared "
                    "only after legal review."
                )
            ),
        ),
        ReadinessCheck(
            "Rights are currently effective",
            rights_dates_valid,
            (
                ""
                if rights_dates_valid
                else "Check Effective from and Effective until."
            ),
        ),
        ReadinessCheck(
            "Required TownLIT usage rights are granted",
            rights_matrix_ready,
            (
                ""
                if rights_matrix_ready
                else (
                    "Missing: "
                    + (
                        ", ".join(missing_rights)
                        if missing_rights
                        else "rights record"
                    )
                    + "."
                )
            ),
        ),
        ReadinessCheck(
            "Territory can be validated by the current publish path",
            territory_ready,
            territory_detail,
        ),
    )

    return TrackReadiness(checks=checks)


def build_search_document(track: MusicTrack) -> str:
    values = [
        track.title,
        track.subtitle,
        track.description,
        track.language_code,
        *track.categories.values_list("name", flat=True),
        *track.genres.values_list("name", flat=True),
        *track.moods.values_list("name", flat=True),
        *track.tags.values_list("name", flat=True),
        *track.contributor_links.values_list(
            "contributor__display_name",
            flat=True,
        ),
    ]

    return " ".join(
        str(value).strip()
        for value in values
        if value and str(value).strip()
    )


@admin.action(description="Publish selected tracks")
def publish_selected(modeladmin, request, queryset):
    eligible = queryset.filter(
        status__in={
            MusicTrack.Status.DRAFT,
            MusicTrack.Status.REVIEW,
        }
    )

    skipped = queryset.exclude(
        status__in={
            MusicTrack.Status.DRAFT,
            MusicTrack.Status.REVIEW,
        }
    ).count()

    succeeded = 0
    failures = []

    for track in eligible.iterator(chunk_size=200):
        try:
            publish_track(track=track, actor=request.user)
            succeeded += 1
        except Exception as exc:
            failures.append(f"{track.title}: {exc}")

    if succeeded:
        modeladmin.message_user(
            request,
            f"{succeeded} track(s) published.",
            level=messages.SUCCESS,
        )

    if skipped:
        modeladmin.message_user(
            request,
            (
                f"{skipped} track(s) skipped because only Draft "
                "or Review tracks can be published from Admin."
            ),
            level=messages.WARNING,
        )

    if failures:
        modeladmin.message_user(
            request,
            " | ".join(failures[:15]),
            level=messages.ERROR,
        )


@admin.action(description="Move selected draft tracks to review")
def move_selected_to_review(modeladmin, request, queryset):
    count = queryset.filter(
        status=MusicTrack.Status.DRAFT
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


@admin.action(description="Move selected tracks back to draft")
def move_selected_to_draft(modeladmin, request, queryset):
    count = queryset.exclude(
        status=MusicTrack.Status.PUBLISHED
    ).update(
        status=MusicTrack.Status.DRAFT,
        suspended_at=None,
        archived_at=None,
        updated_by=request.user,
        updated_at=timezone.now(),
    )

    modeladmin.message_user(
        request,
        f"{count} track(s) moved to draft.",
        level=messages.SUCCESS,
    )


@admin.action(description="Suspend selected published tracks")
def suspend_selected(modeladmin, request, queryset):
    eligible = queryset.filter(status=MusicTrack.Status.PUBLISHED)
    skipped = queryset.exclude(status=MusicTrack.Status.PUBLISHED).count()

    succeeded = 0
    failures = []

    for track in eligible.iterator(chunk_size=200):
        try:
            suspend_track(track=track, actor=request.user)
            succeeded += 1
        except Exception as exc:
            failures.append(f"{track.title}: {exc}")

    if succeeded:
        modeladmin.message_user(
            request,
            f"{succeeded} track(s) suspended.",
            level=messages.WARNING,
        )

    if skipped:
        modeladmin.message_user(
            request,
            f"{skipped} non-published track(s) skipped.",
            level=messages.WARNING,
        )

    if failures:
        modeladmin.message_user(
            request,
            " | ".join(failures[:15]),
            level=messages.ERROR,
        )


@admin.action(description="Archive selected tracks")
def archive_selected(modeladmin, request, queryset):
    count = queryset.exclude(
        status=MusicTrack.Status.ARCHIVED
    ).update(
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


@admin.action(description="Mark selected tracks as test assets")
def mark_as_test_asset(modeladmin, request, queryset):
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


@admin.action(description="Remove test-asset flag")
def remove_test_asset_flag(modeladmin, request, queryset):
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


@admin.action(description="Rebuild search documents")
def rebuild_search_documents(modeladmin, request, queryset):
    prepared = queryset.prefetch_related(
        "categories",
        "genres",
        "moods",
        "tags",
        "contributor_links__contributor",
    )

    updated = 0
    now = timezone.now()

    for track in prepared.iterator(chunk_size=200):
        MusicTrack.objects.filter(pk=track.pk).update(
            search_document=build_search_document(track),
            updated_by=request.user,
            updated_at=now,
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
    Main operational workspace for TownLIT music.

    A normal administrator should be able to create and publish one
    track without leaving this page.
    """

    form = MusicTrackAdminForm
    change_form_template = (
        "admin/audio_catalog/musictrack/change_form.html"
    )

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
        "status",
        "search_document",
        "workflow_intro",
        "readiness_panel",
        "primary_artwork_preview",
        "default_audio_preview",
        "rights_link",
        "advanced_tools_panel",
        "published_at",
        "suspended_at",
        "archived_at",
        "created_at",
        "updated_at",
    )
    actions = (
        publish_selected,
        move_selected_to_review,
        move_selected_to_draft,
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
        MusicRightsRecordInline,
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = (
        "catalog",
        "created_by",
        "updated_by",
        "rights",
        "analytics_metric",
    )

    fieldsets = (
        (
            "Add music",
            {
                "fields": (
                    "workflow_intro",
                    "readiness_panel",
                ),
            },
        ),
        (
            "1. Basic information",
            {
                "fields": (
                    ("catalog", "source_type"),
                    "title",
                    "subtitle",
                    "duration_seconds",
                    "description",
                ),
            },
        ),
        (
            "2. Classification",
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
            "3. Content and usage",
            {
                "fields": (
                    (
                        "is_instrumental",
                        "has_vocals",
                        "is_explicit",
                    ),
                    ("allow_ugc", "allow_streaming"),
                    ("min_clip_seconds", "max_clip_seconds"),
                ),
            },
        ),
        (
            "Current preview",
            {
                "fields": (
                    "primary_artwork_preview",
                    "default_audio_preview",
                    "rights_link",
                ),
            },
        ),
        (
            "Advanced track settings",
            {
                "classes": ("collapse",),
                "fields": (
                    ("bpm", "musical_key", "time_signature"),
                    ("is_ai_assisted", "is_test_asset"),
                    (
                        "allow_standalone_download",
                        "allow_external_export",
                        "allow_commercial_accounts",
                    ),
                    ("sort_order", "popularity_score", "version"),
                    "metadata",
                    "search_document",
                    "status",
                    "public_id",
                    "slug",
                    "published_at",
                    "suspended_at",
                    "archived_at",
                    "created_at",
                    "updated_at",
                    "advanced_tools_panel",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "catalog",
                "created_by",
                "updated_by",
                "rights",
                "analytics_metric",
            )
            .prefetch_related(
                "artworks",
                "variants",
                "contributor_links__contributor",
            )
        )

    def changeform_view(
        self,
        request,
        object_id=None,
        form_url="",
        extra_context=None,
    ):
        extra_context = dict(extra_context or {})

        if object_id:
            obj = self.get_object(request, object_id)

            if obj is not None:
                readiness = evaluate_track_readiness(obj)

                extra_context.update(
                    {
                        "audio_can_publish": readiness.ready,
                        "audio_readiness_missing_count": (
                            readiness.missing_count
                        ),
                        "audio_current_status": obj.status,
                    }
                )

        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    def response_add(self, request, obj, post_url_continue=None):
        if (
            IS_POPUP_VAR in request.POST
            or IS_POPUP_VAR in request.GET
            or "_addanother" in request.POST
        ):
            return super().response_add(
                request,
                obj,
                post_url_continue=post_url_continue,
            )

        self.message_user(
            request,
            (
                f'"{obj.title}" was saved. Stay on this page until '
                "Artwork and Audio conversion show Ready, then "
                "use Publish now."
            ),
            level=messages.SUCCESS,
        )

        return HttpResponseRedirect(
            reverse(
                "admin:audio_catalog_musictrack_change",
                args=[obj.pk],
            )
        )

    def response_change(self, request, obj):
        redirect_url = reverse(
            "admin:audio_catalog_musictrack_change",
            args=[obj.pk],
        )

        if "_move_to_review" in request.POST:
            if obj.status != MusicTrack.Status.DRAFT:
                self.message_user(
                    request,
                    "Only Draft tracks can be moved to Review.",
                    level=messages.ERROR,
                )
            else:
                MusicTrack.objects.filter(pk=obj.pk).update(
                    status=MusicTrack.Status.REVIEW,
                    updated_by=request.user,
                    updated_at=timezone.now(),
                )
                self.message_user(
                    request,
                    "Track moved to Review.",
                    level=messages.SUCCESS,
                )

            return HttpResponseRedirect(redirect_url)

        if "_move_to_draft" in request.POST:
            if obj.status == MusicTrack.Status.PUBLISHED:
                self.message_user(
                    request,
                    (
                        "Published tracks cannot move directly to Draft. "
                        "Suspend the track first."
                    ),
                    level=messages.ERROR,
                )
            else:
                MusicTrack.objects.filter(pk=obj.pk).update(
                    status=MusicTrack.Status.DRAFT,
                    suspended_at=None,
                    archived_at=None,
                    updated_by=request.user,
                    updated_at=timezone.now(),
                )
                self.message_user(
                    request,
                    "Track moved to Draft.",
                    level=messages.SUCCESS,
                )

            return HttpResponseRedirect(redirect_url)

        if "_publish_now" in request.POST:
            if obj.status not in {
                MusicTrack.Status.DRAFT,
                MusicTrack.Status.REVIEW,
            }:
                self.message_user(
                    request,
                    (
                        "Only Draft or Review tracks can be published "
                        "from this workflow."
                    ),
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(redirect_url)

            try:
                publish_track(track=obj, actor=request.user)
            except Exception as exc:
                self.message_user(
                    request,
                    f"Track could not be published: {exc}",
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    "Track published successfully.",
                    level=messages.SUCCESS,
                )

            return HttpResponseRedirect(redirect_url)

        if "_suspend_now" in request.POST:
            if obj.status != MusicTrack.Status.PUBLISHED:
                self.message_user(
                    request,
                    "Only published tracks can be suspended.",
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(redirect_url)

            try:
                suspend_track(track=obj, actor=request.user)
            except Exception as exc:
                self.message_user(
                    request,
                    f"Track could not be suspended: {exc}",
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    "Track suspended.",
                    level=messages.WARNING,
                )

            return HttpResponseRedirect(redirect_url)

        if "_archive_now" in request.POST:
            if obj.status != MusicTrack.Status.ARCHIVED:
                MusicTrack.objects.filter(pk=obj.pk).update(
                    status=MusicTrack.Status.ARCHIVED,
                    archived_at=timezone.now(),
                    updated_by=request.user,
                    updated_at=timezone.now(),
                )

                self.message_user(
                    request,
                    "Track archived.",
                    level=messages.WARNING,
                )

            return HttpResponseRedirect(redirect_url)

        return super().response_change(request, obj)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        Save track inlines and maintain rights review audit metadata.

        Contributor identities are canonical AudioContributor records;
        TrackContributor only stores the track/role relationship.
        """

        now = timezone.now()

        for inline_form in formset.forms:
            cleaned = getattr(inline_form, "cleaned_data", None)

            if not cleaned or cleaned.get("DELETE"):
                continue

            if not (inline_form.instance.pk or inline_form.has_changed()):
                continue

            instance = inline_form.instance

            if isinstance(instance, MusicRightsRecord):
                status_changed = (
                    not instance.pk
                    or "status" in inline_form.changed_data
                )

                if (
                    instance.status
                    in {
                        MusicRightsRecord.Status.CLEARED,
                        MusicRightsRecord.Status.RESTRICTED,
                        MusicRightsRecord.Status.EXPIRED,
                        MusicRightsRecord.Status.REVOKED,
                    }
                    and (status_changed or not instance.reviewed_at)
                ):
                    instance.reviewed_by = request.user
                    instance.reviewed_at = now

                elif (
                    status_changed
                    and instance.status
                    in {
                        MusicRightsRecord.Status.DRAFT,
                        MusicRightsRecord.Status.REVIEW_REQUIRED,
                    }
                ):
                    instance.reviewed_by = None
                    instance.reviewed_at = None

        instances = formset.save(commit=False)

        for deleted in formset.deleted_objects:
            deleted.delete()

        for instance in instances:
            instance.save()

        formset.save_m2m()
        
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        track = form.instance

        MusicTrack.objects.filter(pk=track.pk).update(
            search_document=build_search_document(track),
            updated_by=request.user,
            updated_at=timezone.now(),
        )

    @admin.display(description="Workflow")
    def workflow_intro(self, obj):
        return mark_safe(
            """
            <div style="
                padding:14px 16px;
                border:1px solid var(--border-color);
                border-radius:10px;
                background:var(--darkened-bg);
                color:var(--body-fg);
                line-height:1.55;
            ">
                <strong>Simple music workflow</strong>

                <ol style="margin:8px 0 0 20px;">
                    <li>Enter the basic track information.</li>
                    <li>Upload one cover image below.</li>
                    <li>Upload one playable audio file below.</li>
                    <li>Add credits when applicable.</li>
                    <li>
                        Complete the Rights section and mark it Cleared
                        only after legal review.
                    </li>
                    <li>
                        Save and wait until Artwork and Audio show Ready.
                    </li>
                    <li>Click <strong>Publish now</strong>.</li>
                </ol>

                <div style="
                    margin-top:9px;
                    color:var(--body-quiet-color);
                ">
                    Advanced fields remain available but are collapsed
                    for normal catalog work.
                </div>
            </div>
            """
        )

    @admin.display(description="Publishing readiness")
    def readiness_panel(self, obj):
        if not obj or not obj.pk:
            return (
                "Save the track once to start media conversion "
                "and evaluate publishing readiness."
            )

        readiness = evaluate_track_readiness(obj)

        state = (
            status_badge("Ready to publish", background="#18864b")
            if readiness.ready
            else status_badge(
                f"{readiness.missing_count} requirement(s) need attention",
                background="#c0392b",
            )
        )

        rows = format_html_join(
            "",
            (
                '<li style="margin:8px 0;color:var(--body-fg);">'
                '<span style="display:inline-block;width:22px;">{}</span>'
                "<strong>{}</strong>"
                '<div style="margin-left:22px;'
                'color:var(--body-quiet-color);">{}</div>'
                "</li>"
            ),
            (
                (
                    "✅" if item.ready else "❌",
                    item.label,
                    item.detail,
                )
                for item in readiness.checks
            ),
        )

        return format_html(
            (
                '<div style="padding:14px 16px;'
                'border:1px solid var(--border-color);'
                'border-radius:10px;'
                'background:var(--darkened-bg);'
                'color:var(--body-fg);">'
                "{}"
                '<ul style="list-style:none;padding:0;'
                'margin:10px 0 0 0;">{}</ul>'
                "</div>"
            ),
            state,
            rows,
        )

    @admin.display(description="Artwork")
    def track_artwork(self, obj):
        artwork = next(
            (
                item
                for item in obj.artworks.all()
                if item.is_primary and item.is_active
            ),
            None,
        )

        return render_image_preview(
            getattr(artwork, "image", None),
            width=52,
            height=52,
        )

    @admin.display(description="Track", ordering="title")
    def title_column(self, obj):
        if obj.subtitle:
            return format_html(
                "<strong>{}</strong><br><small>{}</small>",
                obj.title,
                obj.subtitle,
            )

        return format_html("<strong>{}</strong>", obj.title)

    @admin.display(description="Status", ordering="status")
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
            background=color_map.get(obj.status, "#666666"),
        )

    @admin.display(description="Readiness")
    def readiness_display(self, obj):
        readiness = evaluate_track_readiness(obj)

        if readiness.ready:
            return status_badge("Ready", background="#18864b")

        return status_badge(
            f"{readiness.missing_count} missing",
            background="#c0392b",
        )

    @admin.display(description="Default audio")
    def default_audio(self, obj):
        variant = next(
            (
                item
                for item in obj.variants.all()
                if item.is_default and item.is_active
            ),
            None,
        )

        return render_audio_player(
            getattr(variant, "audio_file", None),
            width=230,
        )

    @admin.display(description="Primary artwork")
    def primary_artwork_preview(self, obj):
        if not obj or not obj.pk:
            return "Save the track before adding artwork."

        artwork = next(
            (
                item
                for item in obj.artworks.all()
                if item.is_primary and item.is_active
            ),
            None,
        )

        if artwork is None:
            return "No primary artwork."

        return render_image_preview(
            artwork.image,
            width=260,
            height=260,
        )

    @admin.display(description="Default playback")
    def default_audio_preview(self, obj):
        if not obj or not obj.pk:
            return "Save the track before adding audio."

        variant = next(
            (
                item
                for item in obj.variants.all()
                if item.is_default and item.is_active
            ),
            None,
        )

        if variant is None:
            return "No default playback variant."

        return render_audio_player(
            variant.audio_file,
            width=520,
        )

    @admin.display(description="Rights record")
    def rights_link(self, obj):
        if not obj or not obj.pk:
            return "Save the track first."

        try:
            rights = obj.rights
        except MusicRightsRecord.DoesNotExist:
            return "Complete the Rights section below and save the track."

        return linked_object(
            rights,
            label=(
                f"{rights.get_status_display()} · "
                f"{rights.get_license_type_display()}"
            ),
        )

    @admin.display(description="Advanced tools")
    def advanced_tools_panel(self, obj):
        if not obj or not obj.pk:
            return "—"

        artwork_url = (
            reverse("admin:audio_catalog_musicartwork_changelist")
            + "?"
            + urlencode({"track__id__exact": obj.pk})
        )

        variant_url = (
            reverse("admin:audio_catalog_musictrackvariant_changelist")
            + "?"
            + urlencode({"track__id__exact": obj.pk})
        )

        try:
            rights = obj.rights
        except MusicRightsRecord.DoesNotExist:
            rights = None

        rights_html = (
            linked_object(rights, label="Open full rights editor")
            if rights is not None
            else "No rights record"
        )

        try:
            metric = obj.analytics_metric
        except ObjectDoesNotExist:
            metric = None

        metric_html = (
            linked_object(metric, label="Open track analytics")
            if metric is not None
            else "No analytics yet"
        )

        return format_html(
            (
                '<div style="display:flex;gap:12px;flex-wrap:wrap;'
                'align-items:center;">'
                '<a class="button" href="{}">Artwork manager</a>'
                '<a class="button" href="{}">Audio variants manager</a>'
                "<span>{}</span>"
                "<span>{}</span>"
                "</div>"
            ),
            artwork_url,
            variant_url,
            rights_html,
            metric_html,
        )