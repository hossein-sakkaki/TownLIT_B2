from .strong import TierStrongRelated
from .weak import TierWeakRelated
from .fallback import TierSameTypeFallback


TIERS_BY_KIND = {
    "moment": [
        TierStrongRelated(),
        TierWeakRelated(),
        TierSameTypeFallback(),
    ],
    "testimony": [
        TierStrongRelated(),
        TierWeakRelated(),
        TierSameTypeFallback(),
    ],
}
