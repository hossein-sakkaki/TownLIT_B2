from django.contrib import admin
from django.utils.html import format_html

from apps.subtitles.models import (
    VideoTranscript,
    TranscriptSegment,
    SubtitleTrack,
    VoiceTrack,
    VoiceJobStatus,
)


# -------------------------------------------------
# VideoTranscript
# -------------------------------------------------
@admin.register(VideoTranscript)
class VideoTranscriptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "content_type",
        "object_id",
        "status",
        "source_language",
        "created_at",
        "stt_audio",
        "stt_audio_format",
    )
    list_filter = ("status", "source_language")
    search_fields = ("full_text",)
    readonly_fields = ("created_at", "updated_at")


# -------------------------------------------------
# TranscriptSegment
# -------------------------------------------------
@admin.register(TranscriptSegment)
class TranscriptSegmentAdmin(admin.ModelAdmin):
    list_display = ("id", "transcript", "idx", "start_ms", "end_ms")
    ordering = ("transcript", "idx")
    readonly_fields = ("start_ms", "end_ms")


# -------------------------------------------------
# SubtitleTrack
# -------------------------------------------------
@admin.register(SubtitleTrack)
class SubtitleTrackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transcript",
        "target_language",
        "fmt",
        "status",
        "is_humanized",
        "created_at",
    )
    list_filter = ("target_language", "fmt", "status", "is_humanized")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("content",)


# -------------------------------------------------
# VoiceTrack
# -------------------------------------------------
@admin.register(VoiceTrack)
class VoiceTrackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transcript",
        "target_language",
        "provider",
        "owner_gender",
        "voice_id",
        "colored_status",
        "audio_preview",
        "duration_display",
        "created_at",
    )

    list_filter = (
        "status",
        "target_language",
        "provider",
    )

    search_fields = (
        "spoken_text",
        "error",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "audio_preview",
        "duration_display",
    )

    fieldsets = (
        ("Core", {
            "fields": (
                "transcript",
                "subtitle_track",
                "target_language",
                "provider",
                "voice_id",
                "status",
            )
        }),
        ("Audio Output", {
            "fields": (
                "audio",
                "audio_preview",
                "duration_display",
            )
        }),
        ("Speech Text", {
            "fields": (
                "spoken_text",
            )
        }),
        ("Error / Debug", {
            "fields": (
                "error",
            )
        }),
        ("Meta", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    # -------------------------------------------------
    # Helpers (UI)
    # -------------------------------------------------
    @admin.display(description="Status")
    def colored_status(self, obj: VoiceTrack):
        color = {
            VoiceJobStatus.PENDING: "gray",
            VoiceJobStatus.RUNNING: "orange",
            VoiceJobStatus.DONE: "green",
            VoiceJobStatus.FAILED: "red",
        }.get(obj.status, "black")

        return format_html(
            '<strong style="color:{};">{}</strong>',
            color,
            obj.status.upper(),
        )

    @admin.display(description="Audio")
    def audio_preview(self, obj: VoiceTrack):
        if not obj.audio:
            return "—"

        return format_html(
            '<audio controls preload="none" style="max-width:220px;">'
            '<source src="{}" type="audio/mpeg">'
            "Your browser does not support audio."
            "</audio>",
            obj.audio.url,
        )

    @admin.display(description="Duration")
    def duration_display(self, obj: VoiceTrack):
        if not obj.duration_ms:
            return "—"

        seconds = obj.duration_ms // 1000
        return f"{seconds}s"
