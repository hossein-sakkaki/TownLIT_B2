# apps/audio_catalog/serializers/library.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from rest_framework import serializers

from .catalog import TrackListSerializer


class AudioLibraryTrackSerializer(TrackListSerializer):
    library_entry_id = serializers.UUIDField(read_only=True)
    is_favorite = serializers.BooleanField(
        source="library_is_favorite",
        read_only=True,
    )
    saved_at = serializers.DateTimeField(
        source="library_saved_at",
        read_only=True,
    )
    favorited_at = serializers.DateTimeField(
        source="library_favorited_at",
        read_only=True,
        allow_null=True,
    )

    class Meta(TrackListSerializer.Meta):
        fields = TrackListSerializer.Meta.fields + (
            "library_entry_id",
            "is_favorite",
            "saved_at",
            "favorited_at",
        )


class AudioLibraryStateSerializer(serializers.Serializer):
    is_saved = serializers.BooleanField()
    is_favorite = serializers.BooleanField()
    saved_at = serializers.DateTimeField(allow_null=True)
    favorited_at = serializers.DateTimeField(allow_null=True)


class AudioLibraryStateUpdateSerializer(serializers.Serializer):
    is_saved = serializers.BooleanField()
    is_favorite = serializers.BooleanField()

    def validate(self, attrs):
        if attrs["is_favorite"] and not attrs["is_saved"]:
            raise serializers.ValidationError(
                "A favorite track must also be saved."
            )

        return attrs


class RecentlyPlayedTrackSerializer(TrackListSerializer):
    last_played_at = serializers.DateTimeField(
        source="user_last_played_at",
        read_only=True,
    )

    class Meta(TrackListSerializer.Meta):
        fields = TrackListSerializer.Meta.fields + (
            "last_played_at",
        )