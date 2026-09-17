# apps/core/square/tests/test_square_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db.models import Q
from django.test import SimpleTestCase

from apps.core.square.constants import (
    SQUARE_FRIEND_AFFINITY_FIELD,
    SQUARE_KIND_ALL,
    SQUARE_KIND_FRIENDS,
    normalize_square_kind,
)
from apps.core.square.engines import SquareEngine
from apps.core.square.query import SquareQuery
from apps.core.square.views import SquareViewSet


class SquareViewContractTests(SimpleTestCase):
    def setUp(self):
        self.view = SquareViewSet()
        self.viewer = object()

    def test_score_resolution_matches_requested_mode(self):
        item = SimpleNamespace(
            trending_score=11.0,
            personalized_trending_score=12.0,
            rank_score=13.0,
            hybrid_score=14.0,
        )

        self.assertEqual(
            self.view._score_of(
                item,
                mode=SquareEngine.MODE_TRENDING,
                viewer=self.viewer,
            ),
            11.0,
        )

        self.assertEqual(
            self.view._score_of(
                item,
                mode=SquareEngine.MODE_FOR_YOU,
                viewer=self.viewer,
            ),
            12.0,
        )

        self.assertEqual(
            self.view._score_of(
                item,
                mode=SquareEngine.MODE_RECENT,
                viewer=self.viewer,
            ),
            13.0,
        )

        self.assertEqual(
            self.view._score_of(
                item,
                mode=None,
                viewer=self.viewer,
            ),
            14.0,
        )

    def test_for_you_without_authenticated_viewer_falls_back_to_hybrid_score(
        self,
    ):
        item = SimpleNamespace(
            personalized_trending_score=20.0,
            hybrid_score=8.0,
        )

        self.assertEqual(
            self.view._score_of(
                item,
                mode=SquareEngine.MODE_FOR_YOU,
                viewer=None,
            ),
            8.0,
        )

    def test_multi_source_cursor_uses_score_date_and_id_tuple(self):
        published_at = datetime(
            2026,
            9,
            15,
            12,
            0,
            tzinfo=timezone.utc,
        )

        older_published_at = datetime(
            2026,
            9,
            15,
            11,
            0,
            tzinfo=timezone.utc,
        )

        items = [
            SimpleNamespace(
                id=1,
                published_at=published_at,
                hybrid_score=11.0,
            ),
            SimpleNamespace(
                id=100,
                published_at=published_at,
                hybrid_score=10.0,
            ),
            SimpleNamespace(
                id=99,
                published_at=published_at,
                hybrid_score=10.0,
            ),
            SimpleNamespace(
                id=200,
                published_at=older_published_at,
                hybrid_score=10.0,
            ),
            SimpleNamespace(
                id=300,
                published_at=published_at,
                hybrid_score=9.0,
            ),
        ]

        filtered = self.view._apply_cursor_boundary_multi_source(
            items,
            (
                "s=10.0"
                "&p=2026-09-15T12:00:00+00:00"
                "&id=100"
            ),
            mode=None,
            viewer=self.viewer,
        )

        self.assertEqual(
            [item.id for item in filtered],
            [
                99,
                200,
                300,
            ],
        )


class SquareEngineContractTests(SimpleTestCase):
    @patch(
        "apps.core.square.engines.HybridFeedEngine.apply",
        return_value="hybrid-result",
    )
    @patch(
        "apps.core.square.engines.PersonalizedTrendingEngine.apply",
        return_value="personal-result",
    )
    @patch(
        "apps.core.square.engines.TrendingEngine.apply",
        return_value="trending-result",
    )
    @patch(
        "apps.core.square.engines.FeedRankingEngine.apply",
        return_value="recent-result",
    )
    @patch(
        "apps.core.square.engines."
        "BoundaryVisibilityQuery.exclude_boundary_conflicts",
        return_value="boundary-safe-queryset",
    )
    def test_engine_dispatches_to_existing_ranking_engines(
        self,
        boundary_filter,
        recent_engine,
        trending_engine,
        personal_engine,
        hybrid_engine,
    ):
        viewer = object()

        recent_result = SquareEngine.apply(
            queryset="source-queryset",
            mode=SquareEngine.MODE_RECENT,
            viewer=viewer,
        )

        trending_result = SquareEngine.apply(
            queryset="source-queryset",
            mode=SquareEngine.MODE_TRENDING,
            viewer=viewer,
        )

        personal_result = SquareEngine.apply(
            queryset="source-queryset",
            mode=SquareEngine.MODE_FOR_YOU,
            viewer=viewer,
        )

        hybrid_result = SquareEngine.apply(
            queryset="source-queryset",
            mode=None,
            viewer=viewer,
        )

        self.assertEqual(
            recent_result,
            "recent-result",
        )
        self.assertEqual(
            trending_result,
            "trending-result",
        )
        self.assertEqual(
            personal_result,
            "personal-result",
        )
        self.assertEqual(
            hybrid_result,
            "hybrid-result",
        )

        self.assertEqual(
            boundary_filter.call_count,
            4,
        )

        recent_engine.assert_called_once_with(
            "boundary-safe-queryset",
        )

        trending_engine.assert_called_once_with(
            "boundary-safe-queryset",
        )

        personal_engine.assert_called_once_with(
            "boundary-safe-queryset",
            viewer=viewer,
            friend_affinity_field=SQUARE_FRIEND_AFFINITY_FIELD,
        )

        hybrid_engine.assert_called_once_with(
            "boundary-safe-queryset",
            viewer=viewer,
            friend_affinity_field=SQUARE_FRIEND_AFFINITY_FIELD,
        )

    @patch(
        "apps.core.square.engines.HybridFeedEngine.apply",
        return_value="hybrid-result",
    )
    @patch(
        "apps.core.square.engines.PersonalizedTrendingEngine.apply",
    )
    @patch(
        "apps.core.square.engines."
        "BoundaryVisibilityQuery.exclude_boundary_conflicts",
        return_value="boundary-safe-queryset",
    )
    def test_for_you_without_viewer_falls_back_to_hybrid(
        self,
        _boundary_filter,
        personal_engine,
        hybrid_engine,
    ):
        result = SquareEngine.apply(
            queryset="source-queryset",
            mode=SquareEngine.MODE_FOR_YOU,
            viewer=None,
        )

        self.assertEqual(
            result,
            "hybrid-result",
        )

        personal_engine.assert_not_called()

        hybrid_engine.assert_called_once_with(
            "boundary-safe-queryset",
            viewer=None,
            friend_affinity_field=SQUARE_FRIEND_AFFINITY_FIELD,
        )


class SquareLegacyKindContractTests(SimpleTestCase):
    def test_legacy_friends_kind_normalizes_to_unified_square(self):
        self.assertEqual(
            normalize_square_kind(
                SQUARE_KIND_FRIENDS
            ),
            SQUARE_KIND_ALL,
        )

    def test_empty_kind_normalizes_to_unified_square(self):
        self.assertEqual(
            normalize_square_kind(None),
            SQUARE_KIND_ALL,
        )

        self.assertEqual(
            normalize_square_kind(""),
            SQUARE_KIND_ALL,
        )

        self.assertEqual(
            normalize_square_kind("   "),
            SQUARE_KIND_ALL,
        )

    def test_kind_normalization_is_case_and_whitespace_tolerant(self):
        self.assertEqual(
            normalize_square_kind(
                "  FRIENDS  "
            ),
            SQUARE_KIND_ALL,
        )

        self.assertEqual(
            normalize_square_kind(
                "  MOMENT  "
            ),
            "moment",
        )

    @patch(
        "apps.core.square.views.SquareQuery.build",
        return_value=[],
    )
    def test_legacy_client_request_is_served_as_unified_square(
        self,
        square_query_build,
    ):
        viewer = SimpleNamespace(
            is_authenticated=True,
        )

        request = SimpleNamespace(
            user=viewer,
            query_params={
                "kind": SQUARE_KIND_FRIENDS,
            },
        )

        response = SquareViewSet().list(
            request
        )

        square_query_build.assert_called_once_with(
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.data,
            {
                "next": None,
                "results": [],
            },
        )

    @patch(
        "apps.core.square.query.ContentType.objects.get_for_model",
    )
    @patch(
        "apps.core.square.query.owner_q_for_user_ids",
    )
    @patch(
        "apps.core.square.query.exclude_owned_by_viewer",
    )
    @patch(
        "apps.core.square.query."
        "BoundaryVisibilityQuery.exclude_boundary_conflicts",
    )
    @patch(
        "apps.core.square.query."
        "OwnerVisibilityQuery.filter_queryset_for_square",
    )
    @patch(
        "apps.core.square.query.VisibilityQuery.for_viewer",
    )
    @patch(
        "apps.core.square.query.get_friend_user_ids",
        return_value=[7, 8],
    )
    @patch(
        "apps.core.square.query.get_square_sources",
    )
    def test_legacy_friends_kind_does_not_hard_filter_candidates(
        self,
        get_square_sources,
        get_friend_user_ids,
        visibility_filter,
        owner_visibility_filter,
        boundary_filter,
        exclude_owned,
        owner_q_for_user_ids,
        get_content_type,
    ):
        viewer = object()

        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.annotate.return_value = queryset

        model = MagicMock()
        model.objects.all.return_value = queryset

        source = SimpleNamespace(
            model=model,
            kind="moment",
            requires_conversion=False,
            media_fields=(),
        )

        get_square_sources.return_value = [
            source,
        ]

        visibility_filter.return_value = queryset
        owner_visibility_filter.return_value = queryset
        boundary_filter.return_value = queryset
        exclude_owned.return_value = queryset

        owner_q_for_user_ids.return_value = Q(
            pk__in=[1]
        )

        get_content_type.return_value = SimpleNamespace(
            id=99,
        )

        result = SquareQuery.build(
            viewer=viewer,
            kind=SQUARE_KIND_FRIENDS,
        )

        self.assertEqual(
            result,
            [
                queryset,
            ],
        )

        get_friend_user_ids.assert_called_once_with(
            viewer,
        )

        owner_q_for_user_ids.assert_called_once_with(
            user_ids=[7, 8],
        )

        owner_visibility_filter.assert_called_once_with(
            queryset,
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        # Friendship is annotation/ranking input, not a candidate gate.
        queryset.filter.assert_not_called()

        annotate_kwargs = queryset.annotate.call_args.kwargs

        self.assertIn(
            SQUARE_FRIEND_AFFINITY_FIELD,
            annotate_kwargs,
        )

    @patch(
        "apps.core.square.query.ContentType.objects.get_for_model",
    )
    @patch(
        "apps.core.square.query.exclude_owned_by_viewer",
    )
    @patch(
        "apps.core.square.query."
        "BoundaryVisibilityQuery.exclude_boundary_conflicts",
    )
    @patch(
        "apps.core.square.query."
        "OwnerVisibilityQuery.filter_queryset_for_square",
    )
    @patch(
        "apps.core.square.query.VisibilityQuery.for_viewer",
    )
    @patch(
        "apps.core.square.query.get_friend_user_ids",
        return_value=[],
    )
    @patch(
        "apps.core.square.query.get_square_sources",
    )
    def test_unified_square_without_friends_still_returns_sources(
        self,
        get_square_sources,
        get_friend_user_ids,
        visibility_filter,
        owner_visibility_filter,
        boundary_filter,
        exclude_owned,
        get_content_type,
    ):
        viewer = object()

        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.annotate.return_value = queryset

        model = MagicMock()
        model.objects.all.return_value = queryset

        source = SimpleNamespace(
            model=model,
            kind="moment",
            requires_conversion=False,
            media_fields=(),
        )

        get_square_sources.return_value = [
            source,
        ]

        visibility_filter.return_value = queryset
        owner_visibility_filter.return_value = queryset
        boundary_filter.return_value = queryset
        exclude_owned.return_value = queryset

        get_content_type.return_value = SimpleNamespace(
            id=99,
        )

        result = SquareQuery.build(
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        self.assertEqual(
            result,
            [
                queryset,
            ],
        )

        get_friend_user_ids.assert_called_once_with(
            viewer,
        )

        owner_visibility_filter.assert_called_once_with(
            queryset,
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        annotate_kwargs = queryset.annotate.call_args.kwargs

        self.assertIn(
            SQUARE_FRIEND_AFFINITY_FIELD,
            annotate_kwargs,
        )