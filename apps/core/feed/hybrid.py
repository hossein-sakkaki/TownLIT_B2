# apps/core/feed/hybrid.py

from django.db.models import (
    F,
    FloatField,
    ExpressionWrapper,
    Value,
    Case,
    When,
)
from django.db.models.functions import Coalesce

from apps.core.feed.ranking import FeedRankingEngine
from apps.core.feed.trending import TrendingEngine
from apps.core.feed.constants import (
    HYBRID_FEED_WEIGHT,
    HYBRID_TREND_WEIGHT,
    HYBRID_FRIEND_BOOST,
    HYBRID_COVENANT_BOOST,
    HYBRID_MIN_SCORE,
)
from apps.core.visibility.constants import (
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
)


class HybridFeedEngine:
    """
    Hybrid ranking engine:
    Personalized Feed × Global Trending

    - SQL-only
    - Cursor-safe
    - Content-agnostic
    """

    @staticmethod
    def apply(queryset):
        """
        Apply hybrid feed ranking.
        Assumes:
        - Visibility already filtered
        """

        # -------------------------------------------------
        # 1) Base personalized feed score
        # -------------------------------------------------
        qs = FeedRankingEngine.apply(queryset)

        # feed_score annotated by FeedRankingEngine
        # -------------------------------------------------
        # 2) Trending score
        # -------------------------------------------------
        qs = TrendingEngine.apply(qs)

        # trending_score annotated
        # -------------------------------------------------
        # 3) Relationship-based boost
        # -------------------------------------------------
        relationship_boost = ExpressionWrapper(
            Value(1.0)
            + Case(
                When(
                    visibility=VISIBILITY_COVENANT,
                    then=Value(HYBRID_COVENANT_BOOST - 1),
                ),
                When(
                    visibility=VISIBILITY_FRIENDS,
                    then=Value(HYBRID_FRIEND_BOOST - 1),
                ),
                default=Value(0),
            ),
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 4) Hybrid score (feed × trend × relationship)
        # -------------------------------------------------
        hybrid_score = ExpressionWrapper(
            (
                Coalesce(F("rank_score"), Value(0))
                * Value(HYBRID_FEED_WEIGHT)
            )
            + (
                Coalesce(F("trending_score"), Value(0))
                * Value(HYBRID_TREND_WEIGHT)
            ),
            output_field=FloatField(),
        )

        final_score = ExpressionWrapper(
            hybrid_score * relationship_boost,
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 5) Final ordering (cursor-safe)
        # -------------------------------------------------
        return (
            qs
            .annotate(hybrid_score=final_score)
            .filter(hybrid_score__gt=HYBRID_MIN_SCORE)
            .order_by(
                F("hybrid_score").desc(nulls_last=True),
                F("published_at").desc(),
                F("id").desc(),
            )
        )
