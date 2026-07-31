# apps/posts/admin/testimony.py

from django.contrib import admin, messages
from django.contrib.admin import DateFieldListFilter
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import mark_safe

from apps.posts.admin.filters import TestimonyVideoReviewStatusFilter
from apps.posts.models.testimony import Testimony
from apps.subtitles.models import (
    TranscriptContentReviewStatus,
    TranscriptDetectedContentType,
    VideoTranscript,
)
from apps.subtitles.services.testimony_enforcement import (
    enforce_testimony_review_outcome,
)


def get_testimony_content_type():
    """
    Return the ContentType used by VideoTranscript for Testimony.
    """
    return ContentType.objects.get_for_model(
        Testimony,
        for_concrete_model=False,
    )


def get_testimony_transcript(obj):
    """
    Resolve the transcript linked to a testimony.
    """
    if obj is None or obj.pk is None:
        return None

    try:
        return (
            VideoTranscript.objects
            .filter(
                content_type=get_testimony_content_type(),
                object_id=obj.pk,
            )
            .first()
        )
    except Exception:
        return None


def ensure_testimony_transcript(obj):
    """
    Ensure a VideoTranscript row exists for a video testimony.
    """
    if (
        obj is None
        or obj.pk is None
        or obj.type != Testimony.TYPE_VIDEO
    ):
        return None

    try:
        transcript, _ = VideoTranscript.objects.get_or_create(
            content_type=get_testimony_content_type(),
            object_id=obj.pk,
        )
        return transcript
    except Exception:
        return None


@admin.register(Testimony)
class TestimonyAdmin(admin.ModelAdmin):
    """
    Admin focused on media observability, moderation, and review.
    """

    list_display = (
        "id",
        "slug",
        "type",
        "owner_repr",
        "review_status_badge",
        "review_reason_short",
        "is_active",
        "is_converted",
        "media_flags",
        "published_at",
        "updated_at",
        "visibility",
    )

    list_filter = (
        "type",
        TestimonyVideoReviewStatusFilter,
        "is_active",
        "is_converted",
        "is_hidden",
        "is_suspended",
        ("published_at", DateFieldListFilter),
        "content_type",
    )

    search_fields = (
        "slug",
        "title",
        "content",
        "audio",
        "video",
        "thumbnail",
    )

    ordering = ("-id",)
    list_editable = ("is_active",)
    list_select_related = ("content_type",)
    list_per_page = 50

    # Raw ID fields are retained for large relation datasets.
    raw_id_fields = (
        "user_tags",
        "org_tags",
    )

    readonly_fields = (
        "owner_link",
        "preview_media",
        "file_links",
        "diagnostics",
        "review_status_detail",
        "published_at",
        "updated_at",
        "view_count_internal",
    )

    fieldsets = (
        (
            "Basic",
            {
                "fields": (
                    ("type", "title", "slug"),
                    "content",
                ),
            },
        ),
        (
            "Owner (Generic)",
            {
                "fields": (
                    ("content_type", "object_id"),
                    "owner_link",
                ),
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "thumbnail",
                    "audio",
                    "video",
                    "preview_media",
                    "file_links",
                    "audio_artwork",
                ),
            },
        ),
        (
            "Video Testimony Review",
            {
                "fields": (
                    "review_status_detail",
                ),
            },
        ),
        (
            "Moderation & Visibility",
            {
                "fields": (
                    (
                        "is_active",
                        "is_hidden",
                        "is_suspended",
                        "visibility",
                    ),
                    "reports_count",
                ),
            },
        ),
        (
            "System",
            {
                "fields": (
                    "is_converted",
                    ("published_at", "updated_at"),
                    "diagnostics",
                ),
            },
        ),
        (
            "Tags (optional)",
            {
                "classes": ("collapse",),
                "fields": (
                    "org_tags",
                    "user_tags",
                ),
            },
        ),
    )

    actions = (
        "action_mark_active",
        "action_mark_inactive",
        "action_requeue_conversion",
        "action_rebuild_slug",
        "action_approve_video_testimonies",
        "action_mark_video_testimonies_needs_review",
        "action_reject_and_delete_video_testimonies",
    )

    @admin.display(description="Owner")
    def owner_repr(self, obj):
        content_type = getattr(obj, "content_type", None)
        object_id = getattr(obj, "object_id", None)

        if content_type is None or object_id is None:
            return "-"

        return f"{content_type.model}#{object_id}"

    @admin.display(description="Owner link")
    def owner_link(self, obj):
        content_type = getattr(obj, "content_type", None)
        object_id = getattr(obj, "object_id", None)

        if content_type is None or object_id is None:
            return "-"

        try:
            url = reverse(
                (
                    f"admin:{content_type.app_label}_"
                    f"{content_type.model}_change"
                ),
                args=[object_id],
            )
        except Exception:
            return (
                f"{content_type.app_label}."
                f"{content_type.model} #{object_id}"
            )

        return format_html(
            '<a href="{}">{}.{} #{}</a>',
            url,
            content_type.app_label,
            content_type.model,
            object_id,
        )

    @admin.display(description="Media")
    def media_flags(self, obj):
        audio_flag = "A✔" if getattr(obj, "audio", None) else "A–"
        video_flag = "V✔" if getattr(obj, "video", None) else "V–"
        thumbnail_flag = "T✔" if getattr(obj, "thumbnail", None) else "T–"

        return f"{audio_flag} {video_flag} {thumbnail_flag}"

    @admin.display(description="Preview")
    def preview_media(self, obj):
        parts = []

        try:
            if obj.thumbnail:
                parts.append(
                    format_html(
                        '<div><img src="{}" alt="Thumbnail" '
                        'style="max-width:220px;height:auto;'
                        'border:1px solid #ddd;padding:2px;"></div>',
                        obj.thumbnail.url,
                    )
                )
        except Exception:
            pass

        try:
            if obj.audio:
                parts.append(
                    format_html(
                        '<div style="margin-top:8px;">'
                        '<audio controls preload="metadata" '
                        'style="width:280px;">'
                        '<source src="{}">'
                        'Your browser does not support the audio element.'
                        "</audio>"
                        "</div>",
                        obj.audio.url,
                    )
                )
        except Exception:
            pass

        try:
            if obj.video:
                parts.append(
                    format_html(
                        '<div style="margin-top:8px;">'
                        '<video controls preload="metadata" '
                        'style="max-width:420px;height:auto;">'
                        '<source src="{}" '
                        'type="application/vnd.apple.mpegurl">'
                        "Your browser may not play HLS natively."
                        "</video>"
                        "</div>",
                        obj.video.url,
                    )
                )
        except Exception:
            pass

        if not parts:
            return format_html("<em>No preview</em>")

        return mark_safe("".join(str(part) for part in parts))

    @admin.display(description="File URLs")
    def file_links(self, obj):
        rows = []

        for label in (
            "thumbnail",
            "audio",
            "video",
            "audio_artwork",
        ):
            file_field = getattr(obj, label, None)

            if not file_field:
                rows.append(
                    format_html(
                        "<div><strong>{}</strong>: <em>—</em></div>",
                        label,
                    )
                )
                continue

            file_name = getattr(file_field, "name", "-")

            try:
                rows.append(
                    format_html(
                        '<div><strong>{}</strong>: '
                        '<a href="{}" target="_blank" rel="noopener">'
                        "{}</a></div>",
                        label,
                        file_field.url,
                        file_name,
                    )
                )
            except Exception:
                rows.append(
                    format_html(
                        "<div><strong>{}</strong>: {}</div>",
                        label,
                        file_name,
                    )
                )

        return mark_safe("".join(str(row) for row in rows))

    @admin.display(description="Diagnostics")
    def diagnostics(self, obj):
        issues = []

        if obj.type == Testimony.TYPE_AUDIO:
            if not obj.audio:
                issues.append("Audio testimony has no audio file.")

            if obj.content:
                issues.append("Audio testimony should not have content.")

            if obj.video:
                issues.append("Audio testimony should not have video.")

        elif obj.type == Testimony.TYPE_VIDEO:
            if not obj.video:
                issues.append("Video testimony has no video file.")

            if obj.content:
                issues.append("Video testimony should not have content.")

            if obj.audio:
                issues.append("Video testimony should not have audio.")

        elif obj.type == Testimony.TYPE_WRITTEN:
            if not obj.content:
                issues.append("Written testimony requires content.")

            if obj.audio or obj.video:
                issues.append(
                    "Written testimony should not have audio or video."
                )

        if obj.type in (
            Testimony.TYPE_AUDIO,
            Testimony.TYPE_VIDEO,
        ):
            if not obj.is_converted:
                issues.append(
                    "Media not converted yet (is_converted=False)."
                )

            audio_name = str(
                getattr(getattr(obj, "audio", None), "name", "")
            ).lower()

            if (
                obj.type == Testimony.TYPE_AUDIO
                and audio_name.endswith(".mp3")
                and not obj.is_converted
            ):
                issues.append(
                    "Audio is MP3 but is_converted=False "
                    "(possible no-op conversion case)."
                )

        if not obj.is_active:
            issues.append("Item is inactive.")

        if obj.is_hidden:
            issues.append("Item is hidden.")

        if obj.is_suspended:
            issues.append("Item is suspended.")

        if not issues:
            return format_html(
                '<span style="color:#0a0;">No issues detected</span>'
            )

        items = format_html_join(
            "",
            "<li>{}</li>",
            ((issue,) for issue in issues),
        )

        return format_html(
            '<ul style="margin:0;padding-left:16px;color:#a00;">'
            "{}"
            "</ul>",
            items,
        )

    @admin.display(description="Review")
    def review_status_badge(self, obj):
        if obj.type != Testimony.TYPE_VIDEO:
            return format_html(
                '<span style="color:#777;">—</span>'
            )

        transcript = get_testimony_transcript(obj)

        if transcript is None:
            return format_html(
                '<span style="display:inline-block;padding:3px 8px;'
                'border-radius:10px;background:#555;color:#fff;">'
                "NO TRANSCRIPT"
                "</span>"
            )

        status = (
            transcript.content_review_status
            or "pending"
        )

        color = {
            TranscriptContentReviewStatus.APPROVED: "#2ecc71",
            TranscriptContentReviewStatus.NEEDS_REVIEW: "#f39c12",
            TranscriptContentReviewStatus.REJECTED: "#c0392b",
            "pending": "#7f8c8d",
        }.get(status, "#7f8c8d")

        return format_html(
            '<span style="display:inline-block;padding:3px 8px;'
            'border-radius:10px;background:{};color:#fff;'
            'font-weight:600;">{}</span>',
            color,
            str(status).upper(),
        )

    @admin.display(description="Review reason")
    def review_reason_short(self, obj):
        if obj.type != Testimony.TYPE_VIDEO:
            return "—"

        transcript = get_testimony_transcript(obj)

        if transcript is None:
            return "No transcript"

        reason = transcript.content_review_reason or ""

        if not reason:
            return "—"

        return f"{reason[:80]}…" if len(reason) > 80 else reason

    @admin.display(description="Video review status")
    def review_status_detail(self, obj):
        if obj.type != Testimony.TYPE_VIDEO:
            return format_html(
                "<em>Review is only used for video testimonies.</em>"
            )

        transcript = get_testimony_transcript(obj)

        if transcript is None:
            return format_html(
                '<div style="padding:8px;border:1px solid #ddd;'
                'background:#fff8e1;border-radius:6px;">'
                "<strong>No transcript found.</strong><br>"
                "This video testimony has no VideoTranscript row yet."
                "</div>"
            )

        rows = (
            ("Transcript ID", transcript.id),
            ("Transcript status", getattr(transcript, "status", None)),
            ("Review status", transcript.content_review_status),
            ("Detected type", transcript.detected_content_type),
            ("Confidence", transcript.content_review_confidence),
            ("AI allowed", transcript.ai_processing_allowed),
            ("Reviewed at", transcript.content_reviewed_at),
            (
                "Reason",
                transcript.content_review_reason or "—",
            ),
            (
                "Text preview",
                (transcript.full_text or "")[:500] or "—",
            ),
        )

        table_rows = format_html_join(
            "",
            (
                "<tr>"
                "<th style='text-align:left;padding:4px 10px 4px 0;'>"
                "{}</th>"
                "<td style='padding:4px 0;'>{}</td>"
                "</tr>"
            ),
            (
                (
                    label,
                    value if value is not None else "—",
                )
                for label, value in rows
            ),
        )

        return format_html(
            "<table style='border-collapse:collapse;'>{}</table>",
            table_rows,
        )

    @admin.action(description="Mark selected as Active")
    def action_mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)

        self.message_user(
            request,
            f"{updated} item(s) marked active.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected as Inactive")
    def action_mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)

        self.message_user(
            request,
            f"{updated} item(s) marked inactive.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Requeue media conversion")
    def action_requeue_conversion(self, request, queryset):
        requeued = 0
        failed = 0

        for obj in queryset.iterator():
            try:
                obj.is_converted = False
                obj.save(update_fields=["is_converted"])
                obj.convert_uploaded_media_async()
                requeued += 1
            except Exception as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Failed to requeue testimony {obj.pk}: {exc}",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"{requeued} item(s) requeued. {failed} failed.",
            level=(
                messages.WARNING
                if failed
                else messages.SUCCESS
            ),
        )

    @admin.action(description="Rebuild slug (unique)")
    def action_rebuild_slug(self, request, queryset):
        rebuilt = 0
        failed = 0

        for obj in queryset.iterator():
            try:
                obj.slug = None
                obj.save(update_fields=["slug"])
                rebuilt += 1
            except Exception as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Failed to rebuild slug for {obj.pk}: {exc}",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"{rebuilt} slug(s) rebuilt. {failed} failed.",
            level=(
                messages.WARNING
                if failed
                else messages.SUCCESS
            ),
        )

    def get_search_results(
        self,
        request,
        queryset,
        search_term,
    ):
        result_queryset, use_distinct = super().get_search_results(
            request,
            queryset,
            search_term,
        )

        if search_term.isdigit():
            result_queryset = result_queryset | queryset.filter(
                object_id=int(search_term),
            )

        return result_queryset, use_distinct

    @admin.action(description="Approve selected video testimonies")
    def action_approve_video_testimonies(self, request, queryset):
        approved = 0
        skipped = 0

        for obj in queryset.iterator():
            if obj.type != Testimony.TYPE_VIDEO:
                skipped += 1
                continue

            transcript = ensure_testimony_transcript(obj)

            if transcript is None:
                skipped += 1
                continue

            transcript.content_review_status = (
                TranscriptContentReviewStatus.APPROVED
            )
            transcript.detected_content_type = (
                TranscriptDetectedContentType.PERSONAL_TESTIMONY
            )
            transcript.content_review_confidence = 1.0
            transcript.content_review_reason = (
                "Approved by TownLIT admin review."
            )
            transcript.ai_processing_allowed = True
            transcript.content_reviewed_at = timezone.now()

            transcript.save(
                update_fields=[
                    "content_review_status",
                    "detected_content_type",
                    "content_review_confidence",
                    "content_review_reason",
                    "ai_processing_allowed",
                    "content_reviewed_at",
                    "updated_at",
                ]
            )

            enforce_testimony_review_outcome(transcript)
            approved += 1

        self.message_user(
            request,
            (
                f"{approved} video testimony/testimonies approved. "
                f"{skipped} skipped."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Mark selected video testimonies as Needs Review"
    )
    def action_mark_video_testimonies_needs_review(
        self,
        request,
        queryset,
    ):
        marked = 0
        skipped = 0

        for obj in queryset.iterator():
            if obj.type != Testimony.TYPE_VIDEO:
                skipped += 1
                continue

            transcript = ensure_testimony_transcript(obj)

            if transcript is None:
                skipped += 1
                continue

            transcript.content_review_status = (
                TranscriptContentReviewStatus.NEEDS_REVIEW
            )
            transcript.detected_content_type = (
                transcript.detected_content_type
                or TranscriptDetectedContentType.UNKNOWN
            )

            if transcript.content_review_confidence is None:
                transcript.content_review_confidence = 0.0

            transcript.content_review_reason = (
                transcript.content_review_reason
                or "Marked for manual review by TownLIT admin."
            )
            transcript.ai_processing_allowed = False
            transcript.content_reviewed_at = timezone.now()

            transcript.save(
                update_fields=[
                    "content_review_status",
                    "detected_content_type",
                    "content_review_confidence",
                    "content_review_reason",
                    "ai_processing_allowed",
                    "content_reviewed_at",
                    "updated_at",
                ]
            )

            enforce_testimony_review_outcome(transcript)
            marked += 1

        self.message_user(
            request,
            (
                f"{marked} video testimony/testimonies marked as "
                f"needs review. {skipped} skipped."
            ),
            level=messages.WARNING,
        )

    @admin.action(
        description="Reject and delete selected video testimonies"
    )
    def action_reject_and_delete_video_testimonies(
        self,
        request,
        queryset,
    ):
        deleted = 0
        skipped = 0

        # Materialize IDs because enforcement may delete objects.
        testimony_ids = list(
            queryset.values_list("pk", flat=True)
        )

        for testimony_id in testimony_ids:
            obj = (
                Testimony.objects
                .filter(pk=testimony_id)
                .first()
            )

            if obj is None or obj.type != Testimony.TYPE_VIDEO:
                skipped += 1
                continue

            transcript = ensure_testimony_transcript(obj)

            if transcript is None:
                skipped += 1
                continue

            transcript.content_review_status = (
                TranscriptContentReviewStatus.REJECTED
            )
            transcript.detected_content_type = (
                transcript.detected_content_type
                or TranscriptDetectedContentType.OTHER
            )

            if transcript.content_review_confidence is None:
                transcript.content_review_confidence = 1.0

            transcript.content_review_reason = (
                transcript.content_review_reason
                or (
                    "Rejected by TownLIT admin review because this "
                    "video did not appear to be a personal testimony."
                )
            )
            transcript.ai_processing_allowed = False
            transcript.content_reviewed_at = timezone.now()

            transcript.save(
                update_fields=[
                    "content_review_status",
                    "detected_content_type",
                    "content_review_confidence",
                    "content_review_reason",
                    "ai_processing_allowed",
                    "content_reviewed_at",
                    "updated_at",
                ]
            )

            outcome = enforce_testimony_review_outcome(transcript)

            if outcome == "deleted":
                deleted += 1
            else:
                skipped += 1

        self.message_user(
            request,
            (
                f"{deleted} video testimony/testimonies rejected and "
                f"deleted. {skipped} skipped."
            ),
            level=(
                messages.ERROR
                if deleted
                else messages.WARNING
            ),
        )