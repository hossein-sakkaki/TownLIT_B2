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



class PlaybackBatchItemSerializer(serializers.Serializer):
    """
    One item in a playback batch request.

    Supports both nested target:
    {
        "target": {
            "type": "object",
            "app_label": "conversation",
            "model": "message",
            "object_id": 123
        },
        "field_name": "image",
        "kind": "image",
        "intent": "view"
    }

    and flat target fields for compatibility:
    {
        "app_label": "conversation",
        "model": "message",
        "object_id": 123,
        "field_name": "image",
        "kind": "image",
        "intent": "view"
    }
    """

    target = serializers.DictField(required=False)

    app_label = serializers.CharField(required=False, allow_blank=True)
    model = serializers.CharField(required=False, allow_blank=True)
    object_id = serializers.IntegerField(required=False)
    slug = serializers.CharField(required=False, allow_blank=True)
    content_type_id = serializers.IntegerField(required=False)

    field_name = serializers.CharField()
    kind = serializers.ChoiceField(
        choices=["video", "audio", "image", "thumbnail", "file"]
    )
    intent = serializers.ChoiceField(
        choices=PlaybackIntentChoices.CHOICES,
        required=False,
        default=PlaybackIntentChoices.PRELOAD,
    )


class PlaybackBatchRequestSerializer(serializers.Serializer):
    """
    Batch playback request.

    Keep the limit conservative to protect backend, signing, and permission checks.
    """

    items = serializers.ListField(
        child=PlaybackBatchItemSerializer(),
        min_length=1,
        max_length=20,
    )


class PlaybackBatchResultSerializer(serializers.Serializer):
    """
    One result in a batch response.
    """

    index = serializers.IntegerField()
    ok = serializers.BooleanField()

    asset = PlaybackURLSerializer(required=False)

    error = serializers.CharField(required=False, allow_blank=True)
    status_code = serializers.IntegerField(required=False)


class PlaybackBatchResponseSerializer(serializers.Serializer):
    """
    Stable batch playback response.
    """

    results = serializers.ListField(
        child=PlaybackBatchResultSerializer()
    )