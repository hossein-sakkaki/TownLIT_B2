# apps/core/journey_streams/rail_serializers.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-03.
# Last Update by Hossein Sakkaki on 2026-09-03.

from __future__ import annotations

from rest_framework import serializers

from apps.core.journey_streams.constants import (
    JOURNEY_RAIL_KIND,
)
from apps.core.journey_streams.serializers import (
    JourneyStreamOwnerSerializer,
)


class JourneyRailItemSerializer(
    serializers.Serializer,
):
    """
    Lightweight Journey Rail item.
    """

    kind = serializers.SerializerMethodField()

    journey_id = serializers.IntegerField(
        source="journey.pk",
    )

    journey_slug = serializers.CharField(
        source="journey.slug",
        allow_null=True,
    )

    relationship = serializers.CharField()

    mutual_connector_count = (
        serializers.IntegerField()
    )

    owner = serializers.SerializerMethodField()

    palette_mode = serializers.CharField(
        source="journey.palette_mode",
    )

    active_entries_count = (
        serializers.IntegerField()
    )

    unseen_entries_count = (
        serializers.IntegerField()
    )

    latest_entry_id = serializers.IntegerField()

    expires_at = serializers.DateTimeField()

    next_expiry_at = serializers.DateTimeField()

    def get_kind(self, obj):
        return JOURNEY_RAIL_KIND

    def get_owner(self, obj):
        return JourneyStreamOwnerSerializer(
            obj.owner,
            context=self.context,
        ).data