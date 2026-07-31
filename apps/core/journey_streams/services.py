# apps/core/journey_streams/services.py

from __future__ import annotations

from dataclasses import dataclass

from apps.core.journey_streams.context import (
    JourneyStreamContext,
)
from apps.core.journey_streams.network import (
    JourneyNetworkAudience,
    build_journey_network_audience,
)
from apps.core.journey_streams.query import (
    JourneyStreamPage,
    build_journey_stream_page,
)


@dataclass(frozen=True)
class JourneyStreamResult:
    """
    Complete Journey Stream result.
    """

    audience: JourneyNetworkAudience

    page: JourneyStreamPage


def build_active_journey_stream(
    *,
    context: JourneyStreamContext,
) -> JourneyStreamResult:
    """
    Build the dedicated active Journey Stream.
    """

    audience = (
        build_journey_network_audience(
            viewer=context.viewer,
        )
    )

    page = build_journey_stream_page(
        context=context,
        audience=audience,
    )

    return JourneyStreamResult(
        audience=audience,
        page=page,
    )