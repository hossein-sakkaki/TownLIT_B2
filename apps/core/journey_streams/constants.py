# apps/core/journey_streams/constants.py

from __future__ import annotations


# -------------------------------------------------
# Contracts
# -------------------------------------------------
JOURNEY_STREAM_ACTIVE_CONTRACT = (
    "journey.active.v1"
)

JOURNEY_STREAM_KIND = "journey"


# -------------------------------------------------
# Relationship levels
# -------------------------------------------------
JOURNEY_RELATION_DIRECT = (
    "direct_friend"
)

JOURNEY_RELATION_SECOND_DEGREE = (
    "friend_of_friend"
)

JOURNEY_RELATION_TYPES = {
    JOURNEY_RELATION_DIRECT,
    JOURNEY_RELATION_SECOND_DEGREE,
}


# -------------------------------------------------
# Ranking tiers
# -------------------------------------------------
JOURNEY_RANK_DIRECT_UNSEEN = 400

JOURNEY_RANK_SECOND_DEGREE_UNSEEN = 300

JOURNEY_RANK_DIRECT_SEEN = 200

JOURNEY_RANK_SECOND_DEGREE_SEEN = 100


# -------------------------------------------------
# Pagination
# -------------------------------------------------
JOURNEY_STREAM_DEFAULT_PAGE_SIZE = 12

JOURNEY_STREAM_MAX_PAGE_SIZE = 24


# -------------------------------------------------
# Graph protection
# -------------------------------------------------
JOURNEY_STREAM_MAX_DIRECT_FRIENDS = 500

JOURNEY_STREAM_MAX_SECOND_DEGREE_USERS = 2_000

JOURNEY_STREAM_MAX_CANDIDATE_MEMBERS = 2_000

JOURNEY_STREAM_MAX_CANDIDATE_JOURNEYS = 1_000


# -------------------------------------------------
# Ranking weights
# -------------------------------------------------
JOURNEY_MUTUAL_CONNECTOR_WEIGHT = 10

JOURNEY_UNSEEN_ENTRY_WEIGHT = 4

JOURNEY_ENTRY_COUNT_WEIGHT = 1