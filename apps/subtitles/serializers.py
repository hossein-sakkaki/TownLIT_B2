# apps/subtitles/serializers.py

from __future__ import annotations

from rest_framework import serializers
from apps.subtitles.models import SubtitleTrack, VoiceTrack


# SubtitleTrack serializers -----------------------------------------------------------------
class SubtitleTrackMiniSerializer(serializers.ModelSerializer):
    transcript_id = serializers.SerializerMethodField()

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
            "error",
            "created_at",
            "updated_at",
        ]

    def get_transcript_id(self, obj):
        return obj.transcript_id



# VoiceTrack serializers -------------------------------------------------------------------
class VoiceTrackMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceTrack
        fields = [
            "id",
            "subtitle_track_id",
            "target_language",
            "provider",
            "voice_id",
            "status",
            "duration_ms",
            "error",
            "created_at",
            "updated_at",
        ]
