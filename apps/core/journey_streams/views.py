# apps/core/journey_streams/views.py

from __future__ import annotations

from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.journey_streams.constants import (
    JOURNEY_STREAM_ACTIVE_CONTRACT,
    JOURNEY_STREAM_KIND,
)
from apps.core.journey_streams.context import parse_journey_stream_context
from apps.core.journey_streams.serializers import (
    JourneyFriendStreamSerializer,
)
from apps.core.journey_streams.services import build_active_journey_stream


class JourneyStreamViewSet(viewsets.ViewSet):
    """
    Dedicated Journey Stream.

    Journey is never mixed with Universal Stream content.
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        context = parse_journey_stream_context(request)

        result = build_active_journey_stream(
            context=context,
        )

        journeys = [
            ranked_item.journey
            for ranked_item in result.page.items
        ]

        serializer = JourneyFriendStreamSerializer(
            journeys,
            many=True,
            context={
                "request": request,
                "seen_entry_ids": result.page.seen_entry_ids,
            },
        )

        return Response(
            {
                "contract": JOURNEY_STREAM_ACTIVE_CONTRACT,
                "kind": JOURNEY_STREAM_KIND,
                "generated_at": timezone.now(),
                "next": result.page.next_cursor,
                "has_more": result.page.has_more,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )