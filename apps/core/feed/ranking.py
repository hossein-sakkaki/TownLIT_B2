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
    Central feed ranking engine.
    - SQL-only (no Python loops)
    - MySQL safe
    - Works for any content with InteractionCounterMixin
    """

    @staticmethod
    def apply(queryset):
        """
        Annotates queryset with rank_score
        and applies ordering.
        """

        # ------------------------------
        # Clamp counters (anti-gaming)
        # ------------------------------
        reactions = Least(
            Coalesce(F("reactions_count"), 0),
            Value(MAX_REACTIONS_EFFECT),
        )

        comments = Least(
            Coalesce(F("comments_count"), 0),
            Value(MAX_COMMENTS_EFFECT),
        )

        recomments = Coalesce(F("recomments_count"), 0)

        # ------------------------------
        # Engagement score
        # ------------------------------
        engagement_score = (
            reactions * Value(REACTIONS_WEIGHT)
            + comments * Value(COMMENTS_WEIGHT)
            + recomments * Value(RECOMMENTS_WEIGHT)
        )

        # ------------------------------
        # Age (seconds)
        # ------------------------------
        age_seconds = ExpressionWrapper(
            Now() - F("published_at"),
            output_field=FloatField(),
        )

        # ------------------------------
        # Time decay (smooth, stable)
        # ------------------------------
        decay_factor = ExpressionWrapper(
            1 / (
                1
                + (age_seconds / Value(TIME_DECAY_HOURS * 3600))
            ),
            output_field=FloatField(),
        )

        # ------------------------------
        # Final rank score
        # ------------------------------
        rank_score = ExpressionWrapper(
            engagement_score * decay_factor,
            output_field=FloatField(),
        )

        # ------------------------------
        # Apply annotation + ordering
        # ------------------------------
        return (
            queryset
            .annotate(rank_score=rank_score)
            .order_by(
                F("rank_score").desc(nulls_last=True),
                F("published_at").desc(),
                F("id").desc(),   # tie-break (cursor safe)
            )
        )
