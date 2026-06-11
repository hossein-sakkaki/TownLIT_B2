# apps/subtitles/admin.py

from __future__ import annotations

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import urlencode

from apps.subtitles.models import (
    VideoTranscript,
    TranscriptSegment,
    SubtitleTrack,
    VoiceTrack,
    TranscriptJobStatus,
    SubtitleJobStatus,
    VoiceJobStatus,
    TranscriptContentReviewStatus,
    TranscriptDetectedContentType,
)

from apps.subtitles.services.orchestrator import enqueue_default_subtitles
from apps.subtitles.services.testimony_review import (
    review_and_update_transcript,
)
from apps.subtitles.services.testimony_enforcement import (
    delete_rejected_testimony_media,
    enforce_testimony_review_outcome,
)

from apps.subtitles.tasks import (
    build_transcript_for_video,
    generate_subtitles_task,
    generate_voice_task,
)


# -------------------------------------------------
# Shared helpers
# -------------------------------------------------

def _admin_change_url(obj) -> str | None:
    if not obj:
        return None

    try:
        meta = obj._meta
        return reverse(
            f"admin:{meta.app_label}_{meta.model_name}_change",
            args=[obj.pk],
        )
    except Exception:
        return None


def _status_color(status: str) -> str:
    return {
        "pending": "#6b7280",
        "running": "#f59e0b",
        "done": "#16a34a",
        "failed": "#dc2626",
        "approved": "#16a34a",
        "rejected": "#dc2626",
        "needs_review": "#f59e0b",
        "canceled": "#6b7280",
    }.get(str(status or "").lower(), "#111827")


def _badge(label: str, color: str):
    return format_html(
        '<strong style="color:{};">{}</strong>',
        color,
        str(label or "—").upper(),
    )


# -------------------------------------------------
# Inlines
# -------------------------------------------------

class TranscriptSegmentInline(admin.TabularInline):
    model = TranscriptSegment
    extra = 0
    can_delete = False

    fields = (
        "idx",
        "start_ms",
        "end_ms",
        "text_preview",
    )

    readonly_fields = fields
    ordering = ("idx",)

    @admin.display(description="Text")
    def text_preview(self, obj: TranscriptSegment):
        text = (obj.text or "").strip()
        if not text:
            return "—"

        if len(text) > 180:
            return f"{text[:180]}..."

        return text


class SubtitleTrackInline(admin.TabularInline):
    model = SubtitleTrack
    extra = 0
    can_delete = False

    fields = (
        "target_language",
        "fmt",
        "colored_status",
        "is_humanized",
        "llm_model",
        "prompt_version",
        "error_preview",
        "created_at",
        "updated_at",
    )

    readonly_fields = fields

    @admin.display(description="Status")
    def colored_status(self, obj: SubtitleTrack):
        return _badge(
            obj.status,
            _status_color(obj.status),
        )

    @admin.display(description="Error")
    def error_preview(self, obj: SubtitleTrack):
        error = (obj.error or "").strip()
        if not error:
            return "—"

        if len(error) > 140:
            return f"{error[:140]}..."

        return error


class VoiceTrackInline(admin.TabularInline):
    model = VoiceTrack
    extra = 0
    can_delete = False

    fields = (
        "target_language",
        "provider",
        "voice_id",
        "owner_gender",
        "colored_status",
        "duration_display",
        "audio_preview",
        "error_preview",
        "created_at",
        "updated_at",
    )

    readonly_fields = fields

    @admin.display(description="Status")
    def colored_status(self, obj: VoiceTrack):
        return _badge(
            obj.status,
            _status_color(obj.status),
        )

    @admin.display(description="Audio")
    def audio_preview(self, obj: VoiceTrack):
        if not obj.audio:
            return "—"

        try:
            return format_html(
                '<audio controls preload="none" style="max-width:220px;">'
                '<source src="{}" type="audio/mpeg">'
                "Your browser does not support audio."
                "</audio>",
                obj.audio.url,
            )
        except Exception:
            return "—"

    @admin.display(description="Duration")
    def duration_display(self, obj: VoiceTrack):
        if not obj.duration_ms:
            return "—"

        seconds = obj.duration_ms // 1000
        minutes = seconds // 60
        rest = seconds % 60

        if minutes:
            return f"{minutes}m {rest:02d}s"

        return f"{seconds}s"

    @admin.display(description="Error")
    def error_preview(self, obj: VoiceTrack):
        error = (obj.error or "").strip()
        if not error:
            return "—"

        if len(error) > 140:
            return f"{error[:140]}..."

        return error


# -------------------------------------------------
# VideoTranscript
# -------------------------------------------------

@admin.register(VideoTranscript)
class VideoTranscriptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_link",
        "colored_transcript_status",
        "source_language",
        "colored_review_status",
        "detected_content_type",
        "confidence_display",
        "ai_processing_allowed",
        "has_stt_audio",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "content_review_status",
        "detected_content_type",
        "ai_processing_allowed",
        "source_language",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "id",
        "object_id",
        "full_text",
        "content_review_reason",
        "error",
    )

    readonly_fields = (
        "target_link",
        "content_type",
        "object_id",
        "source_language",
        "stt_engine",
        "stt_model",
        "error",
        "full_text",
        "stt_audio",
        "stt_audio_format",
        "tone_profile",
        "detected_content_type",
        "content_review_confidence",
        "content_review_reason",
        "content_reviewed_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Target",
            {
                "fields": (
                    "target_link",
                    "content_type",
                    "object_id",
                )
            },
        ),
        (
            "Transcript",
            {
                "fields": (
                    "status",
                    "source_language",
                    "stt_engine",
                    "stt_model",
                    "stt_audio",
                    "stt_audio_format",
                    "full_text",
                    "error",
                )
            },
        ),
        (
            "Testimony Review Gate",
            {
                "fields": (
                    "content_review_status",
                    "detected_content_type",
                    "content_review_confidence",
                    "content_review_reason",
                    "ai_processing_allowed",
                    "content_reviewed_at",
                )
            },
        ),
        (
            "Voice / Tone",
            {
                "fields": (
                    "tone_profile",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Meta",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    inlines = (
        TranscriptSegmentInline,
        SubtitleTrackInline,
        VoiceTrackInline,
    )

    actions = (
        "approve_as_personal_testimony",
        "reject_and_delete_testimony",
        "mark_needs_review",
        "rerun_automatic_review",
        "enqueue_subtitles_for_approved",
        "retry_transcript_build",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("content_type")
        )

    # -------------------------------------------------
    # Display helpers
    # -------------------------------------------------

    @admin.display(description="Target")
    def target_link(self, obj: VideoTranscript):
        target = None

        try:
            target = obj.content_object
        except Exception:
            target = None

        label = f"{obj.content_type.app_label}.{obj.content_type.model}#{obj.object_id}"

        url = _admin_change_url(target)
        if not url:
            return label

        return format_html(
            '<a href="{}">{}</a>',
            url,
            label,
        )

    @admin.display(description="Transcript")
    def colored_transcript_status(self, obj: VideoTranscript):
        return _badge(
            obj.status,
            _status_color(obj.status),
        )

    @admin.display(description="Review")
    def colored_review_status(self, obj: VideoTranscript):
        return _badge(
            obj.content_review_status,
            _status_color(obj.content_review_status),
        )

    @admin.display(description="Confidence")
    def confidence_display(self, obj: VideoTranscript):
        if obj.content_review_confidence is None:
            return "—"

        return f"{round(obj.content_review_confidence * 100)}%"

    @admin.display(description="STT audio")
    def has_stt_audio(self, obj: VideoTranscript):
        return bool(obj.stt_audio and obj.stt_audio.name)

    # -------------------------------------------------
    # Actions
    # -------------------------------------------------

    @admin.action(description="Approve as personal testimony and queue subtitles")
    def approve_as_personal_testimony(self, request, queryset):
        approved_count = 0
        queued_count = 0

        for transcript in queryset:
            transcript.content_review_status = TranscriptContentReviewStatus.APPROVED
            transcript.detected_content_type = TranscriptDetectedContentType.PERSONAL_TESTIMONY
            transcript.content_review_confidence = (
                transcript.content_review_confidence
                if transcript.content_review_confidence is not None
                else 1.0
            )
            transcript.content_review_reason = (
                transcript.content_review_reason
                or "Approved manually by admin."
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

            approved_count += 1

            if transcript.status == TranscriptJobStatus.DONE:
                try:
                    enqueue_default_subtitles(transcript)
                    queued_count += 1
                except Exception:
                    self.message_user(
                        request,
                        f"Could not queue subtitles for transcript #{transcript.id}.",
                        level=messages.WARNING,
                    )

        self.message_user(
            request,
            f"{approved_count} transcript(s) approved. "
            f"{queued_count} subtitle pipeline(s) queued.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Reject and delete testimony media")
    def reject_and_delete_testimony(self, request, queryset):
        deleted_count = 0

        for transcript in queryset:
            transcript.content_review_status = TranscriptContentReviewStatus.REJECTED
            transcript.ai_processing_allowed = False
            transcript.content_review_reason = (
                transcript.content_review_reason
                or "Rejected manually by admin because it is not a personal testimony."
            )
            transcript.content_reviewed_at = timezone.now()

            transcript.save(
                update_fields=[
                    "content_review_status",
                    "ai_processing_allowed",
                    "content_review_reason",
                    "content_reviewed_at",
                    "updated_at",
                ]
            )

            try:
                delete_rejected_testimony_media(
                    transcript,
                    reason=transcript.content_review_reason,
                )
                deleted_count += 1
            except Exception:
                self.message_user(
                    request,
                    f"Could not delete rejected testimony for transcript #{transcript.id}.",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"{deleted_count} rejected testimony item(s) deleted.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark as needs review")
    def mark_needs_review(self, request, queryset):
        count = queryset.update(
            content_review_status=TranscriptContentReviewStatus.NEEDS_REVIEW,
            ai_processing_allowed=False,
            content_reviewed_at=timezone.now(),
            updated_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{count} transcript(s) marked as needs review.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Run automatic testimony review again")
    def rerun_automatic_review(self, request, queryset):
        reviewed_count = 0
        deleted_count = 0
        needs_review_count = 0
        approved_count = 0

        for transcript in queryset:
            try:
                transcript = review_and_update_transcript(transcript)
                outcome = enforce_testimony_review_outcome(transcript)

                reviewed_count += 1

                if outcome == "deleted":
                    deleted_count += 1
                elif outcome == "needs_review":
                    needs_review_count += 1
                elif outcome == "approved":
                    approved_count += 1

                    if transcript.status == TranscriptJobStatus.DONE:
                        try:
                            enqueue_default_subtitles(transcript)
                        except Exception:
                            pass

            except Exception:
                self.message_user(
                    request,
                    f"Automatic review failed for transcript #{transcript.id}.",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            (
                f"{reviewed_count} reviewed. "
                f"{approved_count} approved, "
                f"{needs_review_count} needs review, "
                f"{deleted_count} deleted."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(description="Queue subtitles for approved transcripts")
    def enqueue_subtitles_for_approved(self, request, queryset):
        queued_count = 0
        skipped_count = 0

        for transcript in queryset:
            if transcript.status != TranscriptJobStatus.DONE:
                skipped_count += 1
                continue

            if (
                transcript.content_review_status != TranscriptContentReviewStatus.APPROVED
                or transcript.ai_processing_allowed is not True
            ):
                skipped_count += 1
                continue

            try:
                enqueue_default_subtitles(transcript)
                queued_count += 1
            except Exception:
                skipped_count += 1

        self.message_user(
            request,
            f"{queued_count} subtitle pipeline(s) queued. {skipped_count} skipped.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Retry transcript build")
    def retry_transcript_build(self, request, queryset):
        queued_count = 0
        skipped_count = 0

        for transcript in queryset:
            if not transcript.stt_audio or not transcript.stt_audio.name:
                skipped_count += 1
                continue

            if transcript.status == TranscriptJobStatus.RUNNING:
                skipped_count += 1
                continue

            transcript.status = TranscriptJobStatus.PENDING
            transcript.error = ""
            transcript.updated_at = timezone.now()
            transcript.save(update_fields=["status", "error", "updated_at"])

            build_transcript_for_video.delay(transcript.id)
            queued_count += 1

        self.message_user(
            request,
            f"{queued_count} transcript job(s) queued. {skipped_count} skipped.",
            level=messages.SUCCESS,
        )


# -------------------------------------------------
# TranscriptSegment
# -------------------------------------------------

@admin.register(TranscriptSegment)
class TranscriptSegmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transcript_link",
        "idx",
        "start_ms",
        "end_ms",
        "text_preview",
    )

    list_filter = (
        "transcript__source_language",
        "transcript__content_review_status",
    )

    search_fields = (
        "text",
        "transcript__id",
    )

    ordering = (
        "transcript",
        "idx",
    )

    readonly_fields = (
        "transcript",
        "idx",
        "start_ms",
        "end_ms",
        "text",
    )

    @admin.display(description="Transcript")
    def transcript_link(self, obj: TranscriptSegment):
        url = reverse(
            "admin:subtitles_videotranscript_change",
            args=[obj.transcript_id],
        )
        return format_html(
            '<a href="{}">Transcript #{}</a>',
            url,
            obj.transcript_id,
        )

    @admin.display(description="Text")
    def text_preview(self, obj: TranscriptSegment):
        text = (obj.text or "").strip()
        if not text:
            return "—"

        if len(text) > 140:
            return f"{text[:140]}..."

        return text


# -------------------------------------------------
# SubtitleTrack
# -------------------------------------------------

@admin.register(SubtitleTrack)
class SubtitleTrackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transcript_link",
        "target_language",
        "fmt",
        "colored_status",
        "is_humanized",
        "llm_model",
        "prompt_version",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "target_language",
        "fmt",
        "status",
        "is_humanized",
        "transcript__content_review_status",
        "created_at",
    )

    search_fields = (
        "content",
        "error",
        "transcript__id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "content_preview",
    )

    fieldsets = (
        (
            "Core",
            {
                "fields": (
                    "transcript",
                    "target_language",
                    "fmt",
                    "status",
                )
            },
        ),
        (
            "Generation",
            {
                "fields": (
                    "engine",
                    "llm_model",
                    "prompt_version",
                    "is_humanized",
                    "error",
                )
            },
        ),
        (
            "Content Preview",
            {
                "fields": (
                    "content_preview",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Meta",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = (
        "retry_failed_subtitles",
        "regenerate_selected_subtitles",
    )

    @admin.display(description="Transcript")
    def transcript_link(self, obj: SubtitleTrack):
        url = reverse(
            "admin:subtitles_videotranscript_change",
            args=[obj.transcript_id],
        )
        return format_html(
            '<a href="{}">Transcript #{}</a>',
            url,
            obj.transcript_id,
        )

    @admin.display(description="Status")
    def colored_status(self, obj: SubtitleTrack):
        return _badge(
            obj.status,
            _status_color(obj.status),
        )

    @admin.display(description="Content")
    def content_preview(self, obj: SubtitleTrack):
        content = (obj.content or "").strip()
        if not content:
            return "—"

        escaped = content[:3000]
        return format_html(
            '<pre style="white-space:pre-wrap; max-height:420px; overflow:auto;">{}</pre>',
            escaped,
        )

    @admin.action(description="Retry failed subtitles")
    def retry_failed_subtitles(self, request, queryset):
        queued_count = 0
        skipped_count = 0

        for track in queryset.select_related("transcript"):
            if track.status != SubtitleJobStatus.FAILED:
                skipped_count += 1
                continue

            if (
                track.transcript.content_review_status != TranscriptContentReviewStatus.APPROVED
                or track.transcript.ai_processing_allowed is not True
            ):
                skipped_count += 1
                continue

            track.status = SubtitleJobStatus.PENDING
            track.error = ""
            track.updated_at = timezone.now()
            track.save(update_fields=["status", "error", "updated_at"])

            generate_subtitles_task.delay(
                transcript_id=track.transcript_id,
                target_language=track.target_language,
                fmt=track.fmt,
            )

            queued_count += 1

        self.message_user(
            request,
            f"{queued_count} subtitle job(s) queued. {skipped_count} skipped.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Regenerate selected subtitles")
    def regenerate_selected_subtitles(self, request, queryset):
        queued_count = 0
        skipped_count = 0

        for track in queryset.select_related("transcript"):
            if (
                track.transcript.content_review_status != TranscriptContentReviewStatus.APPROVED
                or track.transcript.ai_processing_allowed is not True
            ):
                skipped_count += 1
                continue

            track.status = SubtitleJobStatus.PENDING
            track.error = ""
            track.content = ""
            track.updated_at = timezone.now()
            track.save(update_fields=["status", "error", "content", "updated_at"])

            generate_subtitles_task.delay(
                transcript_id=track.transcript_id,
                target_language=track.target_language,
                fmt=track.fmt,
            )

            queued_count += 1

        self.message_user(
            request,
            f"{queued_count} subtitle regeneration job(s) queued. {skipped_count} skipped.",
            level=messages.SUCCESS,
        )


# -------------------------------------------------
# VoiceTrack
# -------------------------------------------------

@admin.register(VoiceTrack)
class VoiceTrackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transcript_link",
        "subtitle_track",
        "target_language",
        "provider",
        "owner_gender",
        "voice_id",
        "colored_status",
        "audio_preview",
        "duration_display",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "target_language",
        "provider",
        "owner_gender",
        "voice_id",
        "transcript__content_review_status",
        "created_at",
    )

    search_fields = (
        "spoken_text",
        "error",
        "transcript__id",
        "subtitle_track__id",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "audio_preview",
        "duration_display",
    )

    fieldsets = (
        (
            "Core",
            {
                "fields": (
                    "transcript",
                    "subtitle_track",
                    "target_language",
                    "provider",
                    "owner_gender",
                    "voice_id",
                    "status",
                )
            },
        ),
        (
            "Audio Output",
            {
                "fields": (
                    "audio",
                    "audio_preview",
                    "duration_display",
                )
            },
        ),
        (
            "Speech Text",
            {
                "fields": (
                    "spoken_text",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Error / Debug",
            {
                "fields": (
                    "error",
                )
            },
        ),
        (
            "Meta",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = (
        "retry_failed_voices",
        "regenerate_selected_voices",
    )

    @admin.display(description="Transcript")
    def transcript_link(self, obj: VoiceTrack):
        url = reverse(
            "admin:subtitles_videotranscript_change",
            args=[obj.transcript_id],
        )
        return format_html(
            '<a href="{}">Transcript #{}</a>',
            url,
            obj.transcript_id,
        )

    @admin.display(description="Status")
    def colored_status(self, obj: VoiceTrack):
        return _badge(
            obj.status,
            _status_color(obj.status),
        )

    @admin.display(description="Audio")
    def audio_preview(self, obj: VoiceTrack):
        if not obj.audio:
            return "—"

        try:
            return format_html(
                '<audio controls preload="none" style="max-width:220px;">'
                '<source src="{}" type="audio/mpeg">'
                "Your browser does not support audio."
                "</audio>",
                obj.audio.url,
            )
        except Exception:
            return "—"

    @admin.display(description="Duration")
    def duration_display(self, obj: VoiceTrack):
        if not obj.duration_ms:
            return "—"

        seconds = obj.duration_ms // 1000
        minutes = seconds // 60
        rest = seconds % 60

        if minutes:
            return f"{minutes}m {rest:02d}s"

        return f"{seconds}s"

    @admin.action(description="Retry failed voices")
    def retry_failed_voices(self, request, queryset):
        queued_count = 0
        skipped_count = 0

        for track in queryset.select_related("transcript", "subtitle_track"):
            if track.status != VoiceJobStatus.FAILED:
                skipped_count += 1
                continue

            if (
                track.transcript.content_review_status != TranscriptContentReviewStatus.APPROVED
                or track.transcript.ai_processing_allowed is not True
            ):
                skipped_count += 1
                continue

            track.status = VoiceJobStatus.PENDING
            track.error = ""
            track.updated_at = timezone.now()
            track.save(update_fields=["status", "error", "updated_at"])

            generate_voice_task.delay(track.id)
            queued_count += 1

        self.message_user(
            request,
            f"{queued_count} voice job(s) queued. {skipped_count} skipped.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Regenerate selected voices")
    def regenerate_selected_voices(self, request, queryset):
        queued_count = 0
        skipped_count = 0

        for track in queryset.select_related("transcript", "subtitle_track"):
            if (
                track.transcript.content_review_status != TranscriptContentReviewStatus.APPROVED
                or track.transcript.ai_processing_allowed is not True
            ):
                skipped_count += 1
                continue

            track.status = VoiceJobStatus.PENDING
            track.error = ""
            track.audio = None
            track.duration_ms = None
            track.updated_at = timezone.now()
            track.save(
                update_fields=[
                    "status",
                    "error",
                    "audio",
                    "duration_ms",
                    "updated_at",
                ]
            )

            generate_voice_task.delay(track.id)
            queued_count += 1

        self.message_user(
            request,
            f"{queued_count} voice regeneration job(s) queued. {skipped_count} skipped.",
            level=messages.SUCCESS,
        )