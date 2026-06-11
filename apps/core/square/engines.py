# apps/core/square/engines.py

from django.db.models import QuerySet

from apps.core.feed.ranking import FeedRankingEngine
from apps.core.feed.trending import TrendingEngine
from apps.core.feed.personalized_trending import PersonalizedTrendingEngine
from apps.core.feed.hybrid import HybridFeedEngine
from apps.core.boundaries.query import BoundaryVisibilityQuery


class SquareEngine:
    """
    Square ranking orchestrator.

    IMPORTANT:
    - This engine MUST NOT apply ordering.
    - CursorPagination owns ordering entirely.
    - Engines may ONLY annotate and filter.

    Boundary policy:
    - Main Boundary filtering is applied in SquareQuery.
    - This engine keeps a second safety-net filter because some future caller
      may call SquareEngine directly with an unfiltered queryset.

    Stillness policy:
    - Stillness does not affect visibility/ranking.
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
        Apply Square ranking annotations based on mode.

        Returns:
            QuerySet with annotations/filtering only.
            No ordering is applied here.
        """

        # -------------------------------------------------
        # Boundary safety-net
        # -------------------------------------------------
        qs = BoundaryVisibilityQuery.exclude_boundary_conflicts(
            queryset,
            viewer=viewer,
        )

        # -------------------------------------------------
        # Recent: time-decayed engagement score
        # -------------------------------------------------
        if mode == SquareEngine.MODE_RECENT:
            return FeedRankingEngine.apply(qs)

        # -------------------------------------------------
        # Trending: velocity-based score
        # -------------------------------------------------
        if mode == SquareEngine.MODE_TRENDING:
            return TrendingEngine.apply(qs)

        # -------------------------------------------------
        # For You: personalized trending
        # -------------------------------------------------
        if mode == SquareEngine.MODE_FOR_YOU and viewer:
            return PersonalizedTrendingEngine.apply(
                qs,
                viewer=viewer,
            )

        # -------------------------------------------------
        # Default: balanced hybrid score
        # -------------------------------------------------
        return HybridFeedEngine.apply(
            qs,
            viewer=viewer,
        )