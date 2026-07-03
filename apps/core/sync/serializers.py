# apps/core/sync/serializers.py

from rest_framework import serializers


class SyncQuerySerializer(serializers.Serializer):
    """
    Common query params for sync endpoints.
    """

    since = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    cursor = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=50,
    )


class SyncResponseSerializer(serializers.Serializer):
    """
    Common sync response shape.
    """ 

    items = serializers.ListField(
        required=False,
        default=list,
    )
    updated_items = serializers.ListField(
        required=False,
        default=list,
    )
    deleted_ids = serializers.ListField(
        required=False,
        default=list,
    )
    removed_ids = serializers.ListField(
        required=False,
        default=list,
    )
    next_sync_token = serializers.CharField()
    server_time = serializers.CharField()
    has_more = serializers.BooleanField(
        default=False,
    )


class SyncTombstoneSerializer(serializers.Serializer):
    """
    Optional shape for detailed deletion/removal events.
    """

    id = serializers.CharField()
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    occurred_at = serializers.CharField(
        required=False,
        allow_blank=True,
    )