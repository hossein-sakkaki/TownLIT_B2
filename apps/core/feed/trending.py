# apps/core/feed/trending.py

from datetime import timedelta
from django.db.models import (
    F,
    FloatField,
    ExpressionWrapper,
    Value,
    DateTimeField,
    Case,
    When,
)
from django.db.models.functions import (
    Coalesce,
    Now,
    Least,
)

from apps.core.feed.constants import (
    TRENDING_WINDOW_DEFAULT,
    TREND_REACTIONS_WEIGHT,
    TREND_COMMENTS_WEIGHT,
    TREND_RECOMMENTS_WEIGHT,
    TREND_VELOCITY_MULTIPLIER,
    TREND_MAX_REACTIONS,
    TREND_MAX_COMMENTS,
)


class TrendingEngine:
    """
    Trending scoring engine.
    - SQL-only
    - Can either filter by window or only annotate.
    """

    @staticmethod
    def apply(queryset, *, window_seconds=TRENDING_WINDOW_DEFAULT, filter_window: bool = True):
        # -------------------------------------------------
        # 1) Window start expression
        # -------------------------------------------------
        window_start = ExpressionWrapper(
            Now() - Value(timedelta(seconds=window_seconds)),
            output_field=DateTimeField(),
        )

        qs = queryset
        if filter_window:
            qs = qs.filter(published_at__gte=window_start)

        # -------------------------------------------------
        # 2) Clamp counters
        # -------------------------------------------------
        reactions = Least(
            Coalesce(F("reactions_count"), Value(0)),
            Value(TREND_MAX_REACTIONS),
        )
        comments = Least(
            Coalesce(F("comments_count"), Value(0)),
            Value(TREND_MAX_COMMENTS),
        )
        recomments = Coalesce(F("recomments_count"), Value(0))

        # -------------------------------------------------
        # 3) Base engagement score
        # -------------------------------------------------
        base_engagement = (
            reactions * Value(TREND_REACTIONS_WEIGHT)
            + comments * Value(TREND_COMMENTS_WEIGHT)
            + recomments * Value(TREND_RECOMMENTS_WEIGHT)
        )

        # -------------------------------------------------
        # 4) Only score inside window (when not filtering)
        # -------------------------------------------------
        engagement_score = base_engagement
        if not filter_window:
            engagement_score = Case(
                When(published_at__gte=window_start, then=base_engagement),
                default=Value(0.0),
                output_field=FloatField(),
            )

        # -------------------------------------------------
        # 5) Age + velocity
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
            engagement_score / (hours_alive + Value(1.0)),
            output_field=FloatField(),
        )

        # -------------------------------------------------
        # 6) Final trending score
        # -------------------------------------------------
        trending_score = ExpressionWrapper(
            engagement_score + (velocity * Value(TREND_VELOCITY_MULTIPLIER)),
            output_field=FloatField(),
        )

        return qs.annotate(trending_score=trending_score)
