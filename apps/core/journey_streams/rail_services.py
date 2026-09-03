# apps/core/journey_streams/rail_services.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-03.
# Last Update by Hossein Sakkaki on 2026-09-03.

from __future__ import annotations

from dataclasses import dataclass

from apps.core.journey_streams.network import (
    JourneyNetworkAudience,
    build_journey_network_audience,
)
from apps.core.journey_streams.rail_context import (
    JourneyRailContext,
)
from apps.core.journey_streams.rail_query import (
    JourneyRailPage,
    build_journey_rail_page,
)


@dataclass(frozen=True)
class JourneyRailResult:
    """
    Complete Journey Rail result.
    """

    audience: JourneyNetworkAudience
    page: JourneyRailPage


def build_active_journey_rail(
    *,
    context: JourneyRailContext,
) -> JourneyRailResult:
    """
    Build the active Journey Rail.
    """

    audience = (
        build_journey_network_audience(
            viewer=context.viewer,
        )
    )

    page = build_journey_rail_page(
        context=context,
        audience=audience,
    )

    return JourneyRailResult(
        audience=audience,
        page=page,
    )