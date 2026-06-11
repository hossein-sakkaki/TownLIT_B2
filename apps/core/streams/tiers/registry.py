# apps/core/streams/tiers/registry.py

from apps.core.streams.constants import (
    STREAM_KIND_MOMENT,
    STREAM_KIND_TESTIMONY,
    STREAM_KIND_PRAY,
)

from apps.core.streams.tiers.strong import TierSameOwnerSameVisibility
from apps.core.streams.tiers.owner import TierSameOwner
from apps.core.streams.tiers.visibility import TierSameVisibility
from apps.core.streams.tiers.fallback import TierFallback


COMMON_TIERS = [
    TierSameOwnerSameVisibility(),
    TierSameOwner(),
    TierSameVisibility(),
    TierFallback(),
]


TIERS_BY_KIND = {
    STREAM_KIND_MOMENT: COMMON_TIERS,
    STREAM_KIND_TESTIMONY: COMMON_TIERS,
    STREAM_KIND_PRAY: COMMON_TIERS,
}


def get_stream_tiers(kind: str):
    """
    Get tiers for stream kind.
    """

    return TIERS_BY_KIND.get(kind, COMMON_TIERS)