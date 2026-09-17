# apps/core/square/tests/test_square_search.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import (
    MagicMock,
    patch,
)

from django.db.models import QuerySet
from django.test import SimpleTestCase

from apps.core.square.search import (
    SQUARE_SEARCH_MIN_QUERY_LENGTH,
    SquareContentSearch,
)
from apps.core.square.constants import (
    SQUARE_KIND_ALL,
)

class SquareContentSearchContractTests(
    SimpleTestCase
):
    def test_short_query_returns_no_results(
        self,
    ):
        self.assertEqual(
            SquareContentSearch.search(
                viewer=object(),
                query="a",
            ),
            [],
        )

    def test_query_is_trimmed(
        self,
    ):
        self.assertEqual(
            SquareContentSearch.normalize_query(
                "  faith  "
            ),
            "faith",
        )

    def test_minimum_query_length_is_two(
        self,
    ):
        self.assertEqual(
            SQUARE_SEARCH_MIN_QUERY_LENGTH,
            2,
        )

    def test_global_sort_prefers_relevance_then_recency(
        self,
    ):
        newest_contains = SimpleNamespace(
            square_search_rank=2,
            published_at=datetime(
                2026,
                9,
                16,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            square_kind="moment",
            id=3,
        )

        older_exact = SimpleNamespace(
            square_search_rank=0,
            published_at=datetime(
                2026,
                9,
                15,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            square_kind="testimony",
            id=2,
        )

        newer_prefix = SimpleNamespace(
            square_search_rank=1,
            published_at=datetime(
                2026,
                9,
                16,
                11,
                0,
                tzinfo=timezone.utc,
            ),
            square_kind="pray",
            id=4,
        )

        older_prefix = SimpleNamespace(
            square_search_rank=1,
            published_at=datetime(
                2026,
                9,
                14,
                11,
                0,
                tzinfo=timezone.utc,
            ),
            square_kind="moment",
            id=5,
        )

        values = [
            newest_contains,
            older_prefix,
            older_exact,
            newer_prefix,
        ]

        values.sort(
            key=SquareContentSearch._sort_key
        )

        self.assertEqual(
            values,
            [
                older_exact,
                newer_prefix,
                older_prefix,
                newest_contains,
            ],
        )

    @patch(
        "apps.core.square.search.SquareQuery.build",
        return_value=[],
    )
    @patch(
        "apps.core.square.search.get_square_sources",
        return_value=[],
    )
    def test_search_uses_square_eligibility_pipeline(
        self,
        get_square_sources,
        square_query_build,
    ):
        source = SimpleNamespace(
            model=object(),
            search_fields=[
                "caption",
            ],
        )

        get_square_sources.return_value = [
            source,
        ]

        viewer = object()

        result = SquareContentSearch.search(
            viewer=viewer,
            query="faith",
        )

        self.assertEqual(
            result,
            [],
        )

        square_query_build.assert_called_once_with(
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )


class SquareContentSearchFieldTests(
    SimpleTestCase
):
    def test_search_builds_contains_exact_and_prefix_filters(
        self,
    ):
        source = SimpleNamespace(
            search_fields=[
                "title",
                "content",
            ],
        )

        queryset = MagicMock(
            spec=QuerySet
        )

        filtered = MagicMock(
            spec=QuerySet
        )

        annotated = MagicMock(
            spec=QuerySet
        )

        ordered = MagicMock(
            spec=QuerySet
        )

        queryset.filter.return_value = filtered
        filtered.annotate.return_value = annotated
        annotated.order_by.return_value = ordered

        result = SquareContentSearch._apply_search(
            queryset=queryset,
            source=source,
            query="hope",
        )

        self.assertIs(
            result,
            ordered,
        )

        queryset.filter.assert_called_once()
        filtered.annotate.assert_called_once()

        annotated.order_by.assert_called_once_with(
            "square_search_rank",
            "-published_at",
            "-id",
        )