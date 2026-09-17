# apps/core/square/tests/test_square_personalization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.square.constants import SQUARE_KIND_ALL
from apps.core.square.engines import SquareEngine
from apps.core.square.query import SquareQuery


class SquarePersonalizationContractTests(SimpleTestCase):
    FRIEND_AFFINITY_FIELD = "square_is_friend_owner"

    @patch(
        "apps.core.square.query.owner_q_for_user_ids",
    )
    @patch(
        "apps.core.square.query.get_square_sources",
        return_value=[],
    )
    @patch(
        "apps.core.square.query.get_friend_user_ids",
        return_value=[7, 8],
    )
    def test_all_scope_resolves_friend_ids_for_personalization(
        self,
        get_friend_user_ids,
        _get_square_sources,
        owner_q_for_user_ids,
    ):
        viewer = object()

        owner_q_for_user_ids.return_value = object()

        result = SquareQuery.build(
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        self.assertEqual(
            result,
            [],
        )

        get_friend_user_ids.assert_called_once_with(
            viewer,
        )

        owner_q_for_user_ids.assert_called_once_with(
            user_ids=[7, 8],
        )

    @patch(
        "apps.core.square.engines.HybridFeedEngine.apply",
        return_value="hybrid-result",
    )
    @patch(
        "apps.core.square.engines.BoundaryVisibilityQuery.exclude_boundary_conflicts",
        return_value="boundary-safe-queryset",
    )
    def test_default_square_ranking_uses_actual_friend_owner_affinity(
        self,
        _boundary_filter,
        hybrid_engine,
    ):
        viewer = object()

        result = SquareEngine.apply(
            queryset="source-queryset",
            mode=None,
            viewer=viewer,
        )

        self.assertEqual(
            result,
            "hybrid-result",
        )

        hybrid_engine.assert_called_once_with(
            "boundary-safe-queryset",
            viewer=viewer,
            friend_affinity_field=self.FRIEND_AFFINITY_FIELD,
        )

    @patch(
        "apps.core.square.engines.PersonalizedTrendingEngine.apply",
        return_value="personal-result",
    )
    @patch(
        "apps.core.square.engines.BoundaryVisibilityQuery.exclude_boundary_conflicts",
        return_value="boundary-safe-queryset",
    )
    def test_for_you_ranking_uses_actual_friend_owner_affinity(
        self,
        _boundary_filter,
        personal_engine,
    ):
        viewer = object()

        result = SquareEngine.apply(
            queryset="source-queryset",
            mode=SquareEngine.MODE_FOR_YOU,
            viewer=viewer,
        )

        self.assertEqual(
            result,
            "personal-result",
        )

        personal_engine.assert_called_once_with(
            "boundary-safe-queryset",
            viewer=viewer,
            friend_affinity_field=self.FRIEND_AFFINITY_FIELD,
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
        "apps.core.square.query.BoundaryVisibilityQuery.exclude_boundary_conflicts",
    )
    @patch(
        "apps.core.square.query.OwnerVisibilityQuery.filter_queryset_for_square",
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
    def test_all_scope_annotates_actual_friend_owner_affinity(
        self,
        get_square_sources,
        _get_friend_user_ids,
        visibility_filter,
        owner_visibility_filter,
        boundary_filter,
        exclude_owned,
        owner_q_for_user_ids,
        get_content_type,
    ):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

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

        friend_owner_q = MagicMock()
        owner_q_for_user_ids.return_value = friend_owner_q

        get_content_type.return_value = SimpleNamespace(
            id=99,
        )

        SquareQuery.build(
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        owner_q_for_user_ids.assert_called_once_with(
            user_ids=[7, 8],
        )

        annotate_kwargs = queryset.annotate.call_args.kwargs

        self.assertIn(
            self.FRIEND_AFFINITY_FIELD,
            annotate_kwargs,
        )