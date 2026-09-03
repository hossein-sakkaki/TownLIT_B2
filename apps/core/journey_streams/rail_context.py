# apps/core/journey_streams/rail_context.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-03.
# Last Update by Hossein Sakkaki on 2026-09-03.

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from django.utils.dateparse import parse_datetime

from apps.core.journey_streams.constants import (
    JOURNEY_RAIL_DEFAULT_PAGE_SIZE,
    JOURNEY_RAIL_MAX_PAGE_SIZE,
)


@dataclass(frozen=True)
class JourneyRailCursor:
    """
    Stable cursor for Journey Rail.
    """

    relationship_tier: int
    mutual_connector_count: int
    latest_published_at: object
    latest_entry_id: int
    owner_user_id: int


@dataclass(frozen=True)
class JourneyRailContext:
    """
    Normalized Journey Rail request.
    """

    viewer: object
    page_size: int
    cursor: JourneyRailCursor | None


def _parse_page_size(
    raw_value,
) -> int:
    try:
        value = int(
            raw_value
            or JOURNEY_RAIL_DEFAULT_PAGE_SIZE
        )
    except (
        TypeError,
        ValueError,
    ):
        value = JOURNEY_RAIL_DEFAULT_PAGE_SIZE

    return max(
        1,
        min(
            value,
            JOURNEY_RAIL_MAX_PAGE_SIZE,
        ),
    )


def parse_journey_rail_context(
    request,
) -> JourneyRailContext:
    """
    Parse one Rail request.
    """

    return JourneyRailContext(
        viewer=request.user,
        page_size=_parse_page_size(
            request.query_params.get(
                "page_size"
            )
        ),
        cursor=parse_journey_rail_cursor(
            request.query_params.get(
                "cursor"
            )
        ),
    )


def encode_journey_rail_cursor(
    *,
    relationship_tier: int,
    mutual_connector_count: int,
    latest_published_at,
    latest_entry_id: int,
    owner_user_id: int,
) -> str:
    """
    Encode the Rail cursor.
    """

    payload = {
        "relationship_tier": int(
            relationship_tier
        ),
        "mutual_connector_count": int(
            mutual_connector_count
        ),
        "latest_published_at": (
            latest_published_at.isoformat()
        ),
        "latest_entry_id": int(
            latest_entry_id
        ),
        "owner_user_id": int(
            owner_user_id
        ),
    }

    raw = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    return (
        base64
        .urlsafe_b64encode(raw)
        .decode("ascii")
        .rstrip("=")
    )


def parse_journey_rail_cursor(
    raw_value,
) -> JourneyRailCursor | None:
    """
    Decode the Rail cursor.
    """

    if not raw_value:
        return None

    try:
        cleaned = str(raw_value).strip()

        if not cleaned:
            return None

        padding = "=" * (
            -len(cleaned) % 4
        )

        decoded = (
            base64
            .urlsafe_b64decode(
                cleaned + padding
            )
            .decode("utf-8")
        )

        payload = json.loads(decoded)

        tier = int(
            payload[
                "relationship_tier"
            ]
        )

        mutual_count = max(
            int(
                payload[
                    "mutual_connector_count"
                ]
            ),
            0,
        )

        published_at = parse_datetime(
            payload[
                "latest_published_at"
            ]
        )

        entry_id = int(
            payload[
                "latest_entry_id"
            ]
        )

        owner_user_id = int(
            payload[
                "owner_user_id"
            ]
        )

        if (
            tier not in {0, 1}
            or published_at is None
            or entry_id <= 0
            or owner_user_id <= 0
        ):
            return None

        return JourneyRailCursor(
            relationship_tier=tier,
            mutual_connector_count=mutual_count,
            latest_published_at=published_at,
            latest_entry_id=entry_id,
            owner_user_id=owner_user_id,
        )

    except Exception:
        return None