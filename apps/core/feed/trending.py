# apps/core/feed/trending.py

from django.db.models import (
    F,
    FloatField,
    ExpressionWrapper,
    Value,
)
from django.db.models.functions import (
    Coalesce,
    Now,
    Least,
)
from apps.core.feed.constants import (
    TRENDING_WINDOW_24H,
    TREND_REACTIONS_WEIGHT,
    TREND_COMMENTS_WEIGHT,
    TREND_RECOMMENTS_WEIGHT,
    TREND_VELOCITY_MULTIPLIER,
    TREND_MAX_REACTIONS,
    TREND_MAX_COMMENTS,
)


class TrendingEngine:
    """
    Trending ranking engine.
    - Window-based (24h / 7d)
    - Burst & velocity focused
    - SQL-only
    - Content-agnostic (Moment / Testimony / ...)
    """

    @staticmethod
    def apply(queryset, *, window_seconds=TRENDING_WINDOW_24H):
        """
        Apply trending ranking to queryset.
        """

        # -------------------------------------------------
        # 1) Limit to trending window
        # -------------------------------------------------
        qs = queryset.filter(
            published_at__gte=ExpressionWrapper(
                Now() - Value(window_seconds),
                output_field=FloatField(),
            )
        )

        # -------------------------------------------------
        # 2) Clamp counters
        # -------------------------------------------------
        reactions = Least(
            Coalesce(F("reactions_count"), 0),
            Value(TREND_MAX_REACTIONS),
        )

        comments = Least(
            Coalesce(F("comments_count"), 0),
            Value(TREND_MAX_COMMENTS),
        )

        recomments = Coalesce(F("recomments_count"), 0)

        # -------------------------------------------------
        # 3) Raw engagement score
        # -------------------------------------------------
        engagement_score = (
            reactions * Value(TREND_REACTIONS_WEIGHT)
            + comments * Value(TREND_COMMENTS_WEIGHT)
            + recomments * Value(TREND_RECOMMENTS_WEIGHT)
        )

        # -------------------------------------------------
        # 4) Age (seconds → hours)
        # -------------------------------------------------
        age_seconds = ExpressionWrapper(
            Now() - F("published_at"),
            output_field=FloatField(),
        )

        hours_alive = ExpressionWrapper(
            age_seconds / Value(3600),
            output_field=FloatField(),
        )

        velocity = ExpressionWrapper(
            engagement_score / (hours_alive + Value(1)),
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 5) Final trending score
        # -------------------------------------------------
        trending_score = ExpressionWrapper(
            engagement_score
            + (velocity * Value(TREND_VELOCITY_MULTIPLIER)),
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 6) Ordering (stable + cursor safe)
        # -------------------------------------------------
        return (
            qs
            .annotate(trending_score=trending_score)
            .order_by(
                F("trending_score").desc(nulls_last=True),
                F("published_at").desc(),
                F("id").desc(),
            )
        )
