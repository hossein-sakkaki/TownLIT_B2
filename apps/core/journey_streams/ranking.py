# apps/core/journey_streams/ranking.py

from __future__ import annotations

from dataclasses import dataclass

from apps.core.journey_streams.constants import (
    JOURNEY_ENTRY_COUNT_WEIGHT,
    JOURNEY_MUTUAL_CONNECTOR_WEIGHT,
    JOURNEY_RANK_DIRECT_SEEN,
    JOURNEY_RANK_DIRECT_UNSEEN,
    JOURNEY_RANK_SECOND_DEGREE_SEEN,
    JOURNEY_RANK_SECOND_DEGREE_UNSEEN,
    JOURNEY_RELATION_DIRECT,
    JOURNEY_UNSEEN_ENTRY_WEIGHT,
)


@dataclass(frozen=True)
class JourneyRankInput:
    """
    Ranking input for one Journey.
    """

    relationship: str

    mutual_connector_count: int

    unseen_entries_count: int

    active_entries_count: int


def journey_base_rank(
    *,
    relationship: str,
    unseen_entries_count: int,
) -> int:
    """
    Resolve the main ranking tier.
    """

    has_unseen = (
        unseen_entries_count > 0
    )

    if (
        relationship
        == JOURNEY_RELATION_DIRECT
    ):
        return (
            JOURNEY_RANK_DIRECT_UNSEEN
            if has_unseen
            else JOURNEY_RANK_DIRECT_SEEN
        )

    return (
        JOURNEY_RANK_SECOND_DEGREE_UNSEEN
        if has_unseen
        else JOURNEY_RANK_SECOND_DEGREE_SEEN
    )


def calculate_journey_rank(
    rank_input: JourneyRankInput,
) -> int:
    """
    Calculate a deterministic Journey score.
    """

    base = journey_base_rank(
        relationship=(
            rank_input.relationship
        ),
        unseen_entries_count=(
            rank_input
            .unseen_entries_count
        ),
    )

    return int(
        base
        + (
            rank_input
            .mutual_connector_count
            * JOURNEY_MUTUAL_CONNECTOR_WEIGHT
        )
        + (
            rank_input
            .unseen_entries_count
            * JOURNEY_UNSEEN_ENTRY_WEIGHT
        )
        + (
            rank_input
            .active_entries_count
            * JOURNEY_ENTRY_COUNT_WEIGHT
        )
    )