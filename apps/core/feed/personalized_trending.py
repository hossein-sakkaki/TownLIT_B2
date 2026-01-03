# apps/core/feed/personalized_trending.py

from django.db.models import (
    F,
    FloatField,
    ExpressionWrapper,
    Value,
    Q,
    Case,
    When,
)
from django.db.models.functions import Coalesce

from apps.core.feed.trending import TrendingEngine
from apps.core.feed.constants import (
    PERSONAL_TREND_FRIEND_WEIGHT,
    PERSONAL_TREND_COVENANT_WEIGHT,
    PERSONAL_TREND_SELF_WEIGHT,
    PERSONAL_TREND_GLOBAL_WEIGHT,
    PERSONAL_TREND_MIN_SCORE,
)
from apps.core.visibility.constants import (
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
    VISIBILITY_GLOBAL,
)


class PersonalizedTrendingEngine:
    """
    Trending × Relationship affinity
    - SQL-only
    - Viewer-aware
    - Works for any content model
    """

    @staticmethod
    def apply(queryset, *, viewer):
        """
        Apply personalized trending ranking.
        """

        # -------------------------------------------------
        # 1) Base trending (global heat)
        # -------------------------------------------------
        qs = TrendingEngine.apply(queryset)

        # Expect: trending_score annotated

        # -------------------------------------------------
        # 2) Relationship affinity weight
        # -------------------------------------------------
        affinity_weight = Case(
            # Own content
            When(
                object_id=viewer.id,
                then=Value(PERSONAL_TREND_SELF_WEIGHT),
            ),
            # Covenant
            When(
                visibility=VISIBILITY_COVENANT,
                then=Value(PERSONAL_TREND_COVENANT_WEIGHT),
            ),
            # Friends
            When(
                visibility=VISIBILITY_FRIENDS,
                then=Value(PERSONAL_TREND_FRIEND_WEIGHT),
            ),
            # Global / default
            When(
                visibility=VISIBILITY_GLOBAL,
                then=Value(PERSONAL_TREND_GLOBAL_WEIGHT),
            ),
            default=Value(1.0),
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 3) Personalized trending score
        # -------------------------------------------------
        personalized_score = ExpressionWrapper(
            Coalesce(F("trending_score"), Value(0))
            * affinity_weight,
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 4) Final ordering (cursor-safe)
        # -------------------------------------------------
        return (
            qs
            .annotate(personalized_trending_score=personalized_score)
            .filter(personalized_trending_score__gt=PERSONAL_TREND_MIN_SCORE)
            .order_by(
                F("personalized_trending_score").desc(nulls_last=True),
                F("published_at").desc(),
                F("id").desc(),
            )
        )
