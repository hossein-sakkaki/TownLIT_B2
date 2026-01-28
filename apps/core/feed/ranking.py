# apps/core/feed/ranking.py

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
    REACTIONS_WEIGHT,
    COMMENTS_WEIGHT,
    RECOMMENTS_WEIGHT,
    TIME_DECAY_HOURS,
    MAX_REACTIONS_EFFECT,
    MAX_COMMENTS_EFFECT,
)


class FeedRankingEngine:
    """
    Feed ranking engine (time-decayed engagement).
    - SQL-only
    - Annotates rank_score only (no ordering)
    """

    @staticmethod
    def apply(queryset):
        # ------------------------------
        # Clamp counters
        # ------------------------------
        reactions = Least(
            Coalesce(F("reactions_count"), Value(0)),
            Value(MAX_REACTIONS_EFFECT),
        )

        comments = Least(
            Coalesce(F("comments_count"), Value(0)),
            Value(MAX_COMMENTS_EFFECT),
        )

        recomments = Coalesce(F("recomments_count"), Value(0))

        # ------------------------------
        # Engagement score
        # ------------------------------
        engagement_score = (
            reactions * Value(REACTIONS_WEIGHT)
            + comments * Value(COMMENTS_WEIGHT)
            + recomments * Value(RECOMMENTS_WEIGHT)
        )

        # ------------------------------
        # Age + decay
        # ------------------------------
        age_seconds = ExpressionWrapper(
            Now() - F("published_at"),
            output_field=FloatField(),
        )

        decay_factor = ExpressionWrapper(
            Value(1.0)
            / (Value(1.0) + (age_seconds / Value(float(TIME_DECAY_HOURS * 3600)))),
            output_field=FloatField(),
        )

        # ------------------------------
        # Final rank score
        # ------------------------------
        rank_score = ExpressionWrapper(
            engagement_score * decay_factor,
            output_field=FloatField(),
        )

        return queryset.annotate(rank_score=rank_score)
