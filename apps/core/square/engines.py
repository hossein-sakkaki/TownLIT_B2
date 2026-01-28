# apps/core/square/engines.py

from django.db.models import QuerySet

from apps.core.feed.ranking import FeedRankingEngine
from apps.core.feed.trending import TrendingEngine
from apps.core.feed.personalized_trending import PersonalizedTrendingEngine
from apps.core.feed.hybrid import HybridFeedEngine


class SquareEngine:
    """
    Square ranking orchestrator.

    IMPORTANT:
    - This engine MUST NOT apply ordering.
    - CursorPagination owns ordering entirely.
    - Engines may ONLY annotate and filter.
    """

    MODE_RECENT = "recent"
    MODE_TRENDING = "trending"
    MODE_FOR_YOU = "for_you"

    @staticmethod
    def apply(
        *,
        queryset: QuerySet,
        mode: str | None,
        viewer=None,
    ) -> QuerySet:
        """
        Apply ranking annotations based on Square mode.

        Returns:
          QuerySet with annotations ONLY (no ordering).
        """

        # -------------------------------------------------
        # Recent (time-decayed feed score)
        # -------------------------------------------------
        if mode == SquareEngine.MODE_RECENT:
            qs = FeedRankingEngine.apply(queryset)
            return qs

        # -------------------------------------------------
        # Trending (velocity-based)
        # -------------------------------------------------
        if mode == SquareEngine.MODE_TRENDING:
            qs = TrendingEngine.apply(queryset)
            return qs

        # -------------------------------------------------
        # Personalized trending (viewer-aware)
        # -------------------------------------------------
        if mode == SquareEngine.MODE_FOR_YOU and viewer:
            qs = PersonalizedTrendingEngine.apply(
                queryset,
                viewer=viewer,
            )
            return qs

        # -------------------------------------------------
        # Default: Hybrid (balanced Square view)
        # -------------------------------------------------
        qs = HybridFeedEngine.apply(queryset)
        return qs
