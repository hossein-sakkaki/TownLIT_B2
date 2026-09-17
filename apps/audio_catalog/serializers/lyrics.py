# apps/audio_catalog/serializers/lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from rest_framework import serializers

from apps.audio_catalog.models.lyrics import MusicLyrics, MusicLyricsLine
from apps.audio_catalog.models.lyrics_word import MusicLyricsWord


class MusicLyricsQuerySerializer(serializers.Serializer):
    language = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=16,
    )

    kind = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=MusicLyrics.Kind.choices,
    )

    def validate_language(self, value: str) -> str:
        return MusicLyrics.normalize_language_code(value)


class MusicLyricsWordSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(
        source="public_id",
        read_only=True,
    )

    confidence = serializers.FloatField(
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = MusicLyricsWord
        fields = (
            "id",
            "sequence",
            "start_ms",
            "end_ms",
            "text",
            "confidence",
            "is_inferred",
        )
        read_only_fields = fields


class MusicLyricsLineSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(
        source="public_id",
        read_only=True,
    )

    words = MusicLyricsWordSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = MusicLyricsLine
        fields = (
            "id",
            "sequence",
            "start_ms",
            "end_ms",
            "text",
            "words",
        )
        read_only_fields = fields


class MusicLyricsSummarySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(
        source="public_id",
        read_only=True,
    )

    reference_variant_id = serializers.SerializerMethodField()
    is_synchronized = serializers.SerializerMethodField()
    is_word_synchronized = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    word_count = serializers.SerializerMethodField()

    class Meta:
        model = MusicLyrics
        fields = (
            "id",
            "reference_variant_id",
            "language_code",
            "kind",
            "timing_mode",
            "timing_offset_ms",
            "is_default",
            "is_synchronized",
            "is_word_synchronized",
            "line_count",
            "word_count",
            "published_at",
        )
        read_only_fields = fields

    def get_reference_variant_id(self, obj):
        variant = obj.reference_variant
        return variant.public_id if variant is not None else None

    def get_is_synchronized(self, obj) -> bool:
        if obj.timing_mode != MusicLyrics.TimingMode.LINE:
            return False

        lines = list(obj.lines.all())

        return bool(lines) and all(
            line.start_ms is not None
            for line in lines
        )

    def get_is_word_synchronized(self, obj) -> bool:
        if obj.timing_mode != MusicLyrics.TimingMode.LINE:
            return False

        lines = list(obj.lines.all())

        if not lines:
            return False

        for line in lines:
            if line.start_ms is None:
                return False

            words = list(line.words.all())

            if not words:
                return False

            if any(
                word.end_ms <= word.start_ms
                or word.start_ms < line.start_ms
                or (
                    line.end_ms is not None
                    and word.end_ms > line.end_ms
                )
                for word in words
            ):
                return False

        return True

    def get_line_count(self, obj) -> int:
        return len(list(obj.lines.all()))

    def get_word_count(self, obj) -> int:
        return sum(
            len(list(line.words.all()))
            for line in obj.lines.all()
        )


class MusicLyricsSerializer(MusicLyricsSummarySerializer):
    plain_text = serializers.SerializerMethodField()

    lines = MusicLyricsLineSerializer(
        many=True,
        read_only=True,
    )

    class Meta(MusicLyricsSummarySerializer.Meta):
        fields = (
            *MusicLyricsSummarySerializer.Meta.fields,
            "plain_text",
            "lines",
        )
        read_only_fields = fields

    def get_plain_text(self, obj) -> str:
        stored = (obj.plain_text or "").strip()

        if stored:
            return stored

        return "\n".join(
            line.text
            for line in obj.lines.all()
            if (line.text or "").strip()
        )