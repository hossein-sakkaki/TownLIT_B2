# apps/asset_delivery/serializers.py

from rest_framework import serializers


class PlaybackIntentChoices:
    PRELOAD = "preload"
    VIEW = "view"
    RENDER = "render"
    FEED = "feed"
    DETAIL = "detail"
    DOWNLOAD = "download"

    CHOICES = [
        (PRELOAD, "Preload"),
        (VIEW, "View"),
        (RENDER, "Render"),
        (FEED, "Feed"),
        (DETAIL, "Detail"),
        (DOWNLOAD, "Download"),
    ]


class PlaybackAuthModeChoices:
    COOKIE = "cookie"
    SIGNED_URL = "signed_url"

    CHOICES = [
        (COOKIE, "Cookie"),
        (SIGNED_URL, "Signed URL"),
    ]


class PlaybackURLSerializer(serializers.Serializer):
    """
    Stable playback response.

    Backward-compatible:
    - old clients can ignore new fields
    - new clients get richer metadata
    """

    url = serializers.URLField()
    expires_in = serializers.IntegerField()
    expires_at = serializers.DateTimeField(required=False)

    kind = serializers.ChoiceField(
        choices=["video", "audio", "image", "thumbnail", "file"]
    )
    field_name = serializers.CharField()

    # New fields
    auth_mode = serializers.ChoiceField(
        choices=PlaybackAuthModeChoices.CHOICES,
        required=False,
        default=PlaybackAuthModeChoices.COOKIE,
    )
    refreshable = serializers.BooleanField(required=False, default=True)
    cache_key = serializers.CharField(required=False, allow_blank=True)
    intent = serializers.ChoiceField(
        choices=PlaybackIntentChoices.CHOICES,
        required=False,
        default=PlaybackIntentChoices.PRELOAD,
    )

    # Optional extensible metadata
    meta = serializers.DictField(required=False)