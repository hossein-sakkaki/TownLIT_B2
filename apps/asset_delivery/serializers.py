# apps/asset_delivery/serializers.py

from rest_framework import serializers


class PlaybackURLSerializer(serializers.Serializer):
    """
    Stable playback response (forward-compatible).

    - expires_in: seconds (primary)
    - expires_at: ISO timestamp (optional convenience)
    """
    url = serializers.URLField()
    expires_in = serializers.IntegerField()
    expires_at = serializers.DateTimeField(required=False)  # optional
    kind = serializers.ChoiceField(choices=["video", "audio", "image", "thumbnail", "file"])
    field_name = serializers.CharField()
