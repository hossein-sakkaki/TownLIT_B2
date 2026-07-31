# apps/core/journey_streams/context.py

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from django.utils.dateparse import (
    parse_datetime,
)

from apps.core.journey_streams.constants import (
    JOURNEY_STREAM_DEFAULT_PAGE_SIZE,
    JOURNEY_STREAM_MAX_PAGE_SIZE,
)


@dataclass(frozen=True)
class JourneyStreamCursor:
    """
    Stable cursor for ranked Journey results.
    """

    rank_score: int

    latest_published_at: object

    latest_entry_id: int


@dataclass(frozen=True)
class JourneyStreamContext:
    """
    Normalized Journey Stream request.
    """

    viewer: object

    page_size: int

    cursor: JourneyStreamCursor | None


def _parse_page_size(
    raw_value,
) -> int:
    try:
        value = int(
            raw_value
            or JOURNEY_STREAM_DEFAULT_PAGE_SIZE
        )

    except (
        TypeError,
        ValueError,
    ):
        value = (
            JOURNEY_STREAM_DEFAULT_PAGE_SIZE
        )

    return max(
        1,
        min(
            value,
            JOURNEY_STREAM_MAX_PAGE_SIZE,
        ),
    )


def parse_journey_stream_context(
    request,
) -> JourneyStreamContext:
    """
    Parse Journey Stream request.
    """

    return JourneyStreamContext(
        viewer=request.user,
        page_size=_parse_page_size(
            request.query_params.get(
                "page_size"
            )
        ),
        cursor=parse_journey_stream_cursor(
            request.query_params.get(
                "cursor"
            )
        ),
    )


def encode_journey_stream_cursor(
    *,
    rank_score: int,
    latest_published_at,
    latest_entry_id: int,
) -> str:
    """
    Encode a URL-safe ranked cursor.
    """

    payload = {
        "rank_score": int(
            rank_score
        ),
        "latest_published_at": (
            latest_published_at
            .isoformat()
        ),
        "latest_entry_id": int(
            latest_entry_id
        ),
    }

    raw = json.dumps(
        payload,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return (
        base64
        .urlsafe_b64encode(
            raw
        )
        .decode(
            "ascii"
        )
        .rstrip("=")
    )


def parse_journey_stream_cursor(
    raw_value,
) -> JourneyStreamCursor | None:
    """
    Decode a ranked Journey cursor.
    """

    if not raw_value:
        return None

    try:
        cleaned = str(
            raw_value
        ).strip()

        if not cleaned:
            return None

        padding = (
            "="
            * (
                -len(cleaned)
                % 4
            )
        )

        decoded = (
            base64
            .urlsafe_b64decode(
                cleaned
                + padding
            )
            .decode(
                "utf-8"
            )
        )

        payload = json.loads(
            decoded
        )

        rank_score = int(
            payload[
                "rank_score"
            ]
        )

        latest_published_at = (
            parse_datetime(
                payload[
                    "latest_published_at"
                ]
            )
        )

        latest_entry_id = int(
            payload[
                "latest_entry_id"
            ]
        )

        if (
            latest_published_at is None
            or latest_entry_id <= 0
        ):
            return None

        return JourneyStreamCursor(
            rank_score=rank_score,
            latest_published_at=(
                latest_published_at
            ),
            latest_entry_id=(
                latest_entry_id
            ),
        )

    except Exception:
        return None