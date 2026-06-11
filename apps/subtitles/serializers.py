# apps/subtitles/serializers.py

from __future__ import annotations
from rest_framework import serializers
from apps.subtitles.models import SubtitleTrack, VoiceTrack, VideoTranscript


# SubtitleTrack serializers -----------------------------------------------------------------
class SubtitleTrackMiniSerializer(serializers.ModelSerializer):
    transcript_id = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()
    playback_url = serializers.SerializerMethodField()

    class Meta:
        model = SubtitleTrack
        fields = [
            "id",
            "transcript_id",
            "target_language",
            "fmt",
            "status",
            "engine",
            "is_humanized",
            "llm_model",
            "prompt_version",
            "content_url",
            "playback_url",
            "error",
            "created_at",
            "updated_at",
        ]

    def get_transcript_id(self, obj):
        return obj.transcript_id

    def get_content_url(self, obj):
        """
        Return a playable subtitle content URL only when content is ready.
        """
        if not getattr(obj, "content", ""):
            return None

        return self._absolute_url(f"/api/v1/subtitles/tracks/{obj.id}/content/")

    def get_playback_url(self, obj):
        """
        Alias for clients that prefer playback_url.
        """
        return self.get_content_url(obj)

    def _absolute_url(self, path: str):
        request = self.context.get("request")

        if request is not None:
            return request.build_absolute_uri(path)

        return path


# VoiceTrack serializers -------------------------------------------------------------------
class VoiceTrackMiniSerializer(serializers.ModelSerializer):
    content_url = serializers.SerializerMethodField()
    playback_url = serializers.SerializerMethodField()

    class Meta:
        model = VoiceTrack
        fields = [
            "id",
            "subtitle_track_id",
            "target_language",
            "provider",
            "voice_id",
            "status",
            "content_url",
            "playback_url",
            "duration_ms",
            "error",
            "created_at",
            "updated_at",
        ]

    def get_content_url(self, obj):
        """
        Return a playable voice content URL only when audio is ready.
        """
        if not getattr(obj, "audio", None):
            return None

        return self._absolute_url(f"/api/v1/subtitles/voices/{obj.id}/content/")

    def get_playback_url(self, obj):
        """
        Alias for clients that prefer playback_url.
        """
        return self.get_content_url(obj)

    def _absolute_url(self, path: str):
        request = self.context.get("request")

        if request is not None:
            return request.build_absolute_uri(path)

        return path


class VideoTranscriptMiniSerializer(serializers.ModelSerializer):
    content_type_model = serializers.SerializerMethodField()

    class Meta:
        model = VideoTranscript
        fields = [
            "id",
            "content_type_model",
            "object_id",
            "status",
            "source_language",
            "stt_model",
            "error",
            "content_review_status",
            "detected_content_type",
            "content_review_confidence",
            "content_review_reason",
            "ai_processing_allowed",
            "content_reviewed_at",
            "created_at",
            "updated_at",
        ]

    def get_content_type_model(self, obj):
        try:
            return f"{obj.content_type.app_label}.{obj.content_type.model}"
        except Exception:
            return ""