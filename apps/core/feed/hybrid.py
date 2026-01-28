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
    HYBRID_ENABLE_MIN_ENGAGEMENT,
)
from apps.core.visibility.constants import (
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
)


class HybridFeedEngine:
    """
    Hybrid: Feed rank + Trending heat (when engagement exists).
    - Annotate only (no ordering, no dropping content)
    """

    @staticmethod
    def apply(queryset):
        # 1) Base feed score
        qs = FeedRankingEngine.apply(queryset)

        # 2) Trending score (annotate-only; do NOT filter by window)
        qs = TrendingEngine.apply(qs, filter_window=False)

        # 3) Relationship boost
        relationship_boost = ExpressionWrapper(
            Value(1.0)
            + Case(
                When(
                    visibility=VISIBILITY_COVENANT,
                    then=Value(float(HYBRID_COVENANT_BOOST - 1)),
                ),
                When(
                    visibility=VISIBILITY_FRIENDS,
                    then=Value(float(HYBRID_FRIEND_BOOST - 1)),
                ),
                default=Value(0.0),
            ),
            output_field=FloatField(),
        )

        # 4) Engagement total (annotate FIRST so we can reference it in When lookups)
        engagement_total_expr = ExpressionWrapper(
            Coalesce(F("reactions_count"), Value(0))
            + Coalesce(F("comments_count"), Value(0))
            + Coalesce(F("recomments_count"), Value(0)),
            output_field=FloatField(),
        )

        qs = qs.annotate(engagement_total=engagement_total_expr)

        # 5) Weighted hybrid
        weighted_hybrid = ExpressionWrapper(
            (Coalesce(F("rank_score"), Value(0.0)) * Value(HYBRID_FEED_WEIGHT))
            + (Coalesce(F("trending_score"), Value(0.0)) * Value(HYBRID_TREND_WEIGHT)),
            output_field=FloatField(),
        )

        # 6) Early-phase fallback (no trend blending if engagement is too low)
        safe_hybrid = Case(
            When(
                engagement_total__lt=Value(float(HYBRID_ENABLE_MIN_ENGAGEMENT)),
                then=Coalesce(F("rank_score"), Value(0.0)),
            ),
            default=weighted_hybrid,
            output_field=FloatField(),
        )

        final_score = ExpressionWrapper(
            safe_hybrid * relationship_boost,
            output_field=FloatField(),
        )

        return qs.annotate(hybrid_score=final_score)
