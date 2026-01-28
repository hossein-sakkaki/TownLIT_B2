# apps/core/feed/personalized_trending.py

from django.db.models import (
    F,
    FloatField,
    ExpressionWrapper,
    Value,
    Case,
    When,
)
from django.db.models.functions import Coalesce

from apps.core.feed.trending import TrendingEngine
from apps.core.feed.ranking import FeedRankingEngine
from apps.core.feed.constants import (
    PERSONAL_TREND_FRIEND_WEIGHT,
    PERSONAL_TREND_COVENANT_WEIGHT,
    PERSONAL_TREND_SELF_WEIGHT,
    PERSONAL_TREND_GLOBAL_WEIGHT,
    PERSONAL_TREND_ENABLE_MIN_ENGAGEMENT,
)
from apps.core.visibility.constants import (
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
    VISIBILITY_GLOBAL,
)


class PersonalizedTrendingEngine:
    """
    Personalized trending = trending_score * affinity.
    Early phase: fallback to rank_score if engagement is low.
    """

    @staticmethod
    def apply(queryset, *, viewer):
        # 1) Trending annotate-only (do NOT drop content)
        qs = TrendingEngine.apply(queryset, filter_window=False)

        # 2) Rank score for fallback
        qs = FeedRankingEngine.apply(qs)

        # 3) Affinity weight
        affinity_weight = Case(
            When(object_id=viewer.id, then=Value(PERSONAL_TREND_SELF_WEIGHT)),
            When(visibility=VISIBILITY_COVENANT, then=Value(PERSONAL_TREND_COVENANT_WEIGHT)),
            When(visibility=VISIBILITY_FRIENDS, then=Value(PERSONAL_TREND_FRIEND_WEIGHT)),
            When(visibility=VISIBILITY_GLOBAL, then=Value(PERSONAL_TREND_GLOBAL_WEIGHT)),
            default=Value(1.0),
            output_field=FloatField(),
        )

        # 4) Engagement total (annotate FIRST)
        engagement_total_expr = ExpressionWrapper(
            Coalesce(F("reactions_count"), Value(0))
            + Coalesce(F("comments_count"), Value(0))
            + Coalesce(F("recomments_count"), Value(0)),
            output_field=FloatField(),
        )
        qs = qs.annotate(engagement_total=engagement_total_expr)

        # 5) Personalized score (weighted)
        weighted_personal = ExpressionWrapper(
            Coalesce(F("trending_score"), Value(0.0)) * affinity_weight,
            output_field=FloatField(),
        )

        # 6) Early-phase fallback
        safe_personal = Case(
            When(
                engagement_total__lt=Value(float(PERSONAL_TREND_ENABLE_MIN_ENGAGEMENT)),
                then=Coalesce(F("rank_score"), Value(0.0)),
            ),
            default=weighted_personal,
            output_field=FloatField(),
        )

        return qs.annotate(personalized_trending_score=safe_personal)
