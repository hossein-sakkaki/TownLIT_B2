# apps/core/square/stream/tiers/registry.py

from .strong import TierStrongRelated
from .weak import TierWeakRelated
from .fallback import TierSameTypeFallback


COMMON_TIERS = [TierStrongRelated(), TierWeakRelated(), TierSameTypeFallback()]

TIERS_BY_KIND = {
    "moment": COMMON_TIERS,
    "testimony": COMMON_TIERS,
    "pray": COMMON_TIERS,
}