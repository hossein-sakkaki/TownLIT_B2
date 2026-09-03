# apps/core/journey_streams/views.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-03.
# Last Update by Hossein Sakkaki on 2026-09-03.

from __future__ import annotations

from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.core.journey_streams.constants import (
    JOURNEY_RAIL_ACTIVE_CONTRACT,
    JOURNEY_RAIL_KIND,
    JOURNEY_STREAM_ACTIVE_CONTRACT,
    JOURNEY_STREAM_KIND,
)
from apps.core.journey_streams.context import (
    parse_journey_stream_context,
)
from apps.core.journey_streams.rail_context import (
    parse_journey_rail_context,
)
from apps.core.journey_streams.rail_serializers import (
    JourneyRailItemSerializer,
)
from apps.core.journey_streams.rail_services import (
    build_active_journey_rail,
)
from apps.core.journey_streams.serializers import (
    JourneyFriendStreamSerializer,
)
from apps.core.journey_streams.services import (
    build_active_journey_stream,
)


class JourneyStreamViewSet(
    viewsets.ViewSet,
):
    """
    Journey Stream and Rail surfaces.
    """

    permission_classes = [
        IsAuthenticated
    ]

    def list(
        self,
        request,
    ):
        context = (
            parse_journey_stream_context(
                request
            )
        )

        result = build_active_journey_stream(
            context=context,
        )

        journeys = [
            ranked_item.journey
            for ranked_item
            in result.page.items
        ]

        serializer = (
            JourneyFriendStreamSerializer(
                journeys,
                many=True,
                context={
                    "request": request,
                    "seen_entry_ids": (
                        result.page
                        .seen_entry_ids
                    ),
                },
            )
        )

        return Response(
            {
                "contract": (
                    JOURNEY_STREAM_ACTIVE_CONTRACT
                ),
                "kind": JOURNEY_STREAM_KIND,
                "generated_at": timezone.now(),
                "next": result.page.next_cursor,
                "has_more": result.page.has_more,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def rail(
        self,
        request,
    ):
        context = (
            parse_journey_rail_context(
                request
            )
        )

        result = build_active_journey_rail(
            context=context,
        )

        serializer = JourneyRailItemSerializer(
            result.page.items,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "contract": (
                    JOURNEY_RAIL_ACTIVE_CONTRACT
                ),
                "kind": JOURNEY_RAIL_KIND,
                "generated_at": timezone.now(),
                "next": result.page.next_cursor,
                "has_more": result.page.has_more,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )