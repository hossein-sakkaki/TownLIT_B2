# apps/core/square/search.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from django.db.models import (
    Case,
    IntegerField,
    Q,
    QuerySet,
    Value,
    When,
)

from apps.core.square.constants import (
    SQUARE_KIND_ALL,
)
from apps.core.square.query import SquareQuery
from apps.core.square.registry import (
    SquareContentSource,
    get_square_sources,
)


SQUARE_SEARCH_MIN_QUERY_LENGTH = 2
SQUARE_SEARCH_SOURCE_CANDIDATE_LIMIT = 100


class SquareContentSearch:
    """
    Search Square-eligible content across registered sources.

    Visibility and eligibility are inherited from SquareQuery.
    Search ranking is text relevance first, then recency.
    """

    @classmethod
    def search(
        cls,
        *,
        viewer,
        query: str,
    ) -> list:
        cleaned_query = cls.normalize_query(
            query
        )

        if len(cleaned_query) < (
            SQUARE_SEARCH_MIN_QUERY_LENGTH
        ):
            return []

        sources_by_model = {
            source.model: source
            for source in get_square_sources()
            if source.search_fields
        }

        if not sources_by_model:
            return []

        querysets = SquareQuery.build(
            viewer=viewer,
            kind=SQUARE_KIND_ALL,
        )

        merged = []

        for queryset in querysets:
            source = sources_by_model.get(
                queryset.model
            )

            if source is None:
                continue

            ranked_queryset = (
                cls._apply_search(
                    queryset=queryset,
                    source=source,
                    query=cleaned_query,
                )
            )

            merged.extend(
                list(
                    ranked_queryset[
                        :SQUARE_SEARCH_SOURCE_CANDIDATE_LIMIT
                    ]
                )
            )

        merged.sort(
            key=cls._sort_key
        )

        return merged

    @classmethod
    def _apply_search(
        cls,
        *,
        queryset: QuerySet,
        source: SquareContentSource,
        query: str,
    ) -> QuerySet:
        contains_filter = Q()
        exact_filter = Q()
        prefix_filter = Q()

        for field_name in source.search_fields:
            contains_filter |= Q(
                **{
                    f"{field_name}__icontains":
                        query,
                }
            )

            exact_filter |= Q(
                **{
                    f"{field_name}__iexact":
                        query,
                }
            )

            prefix_filter |= Q(
                **{
                    f"{field_name}__istartswith":
                        query,
                }
            )

        return (
            queryset
            .filter(
                contains_filter
            )
            .annotate(
                square_search_rank=Case(
                    When(
                        exact_filter,
                        then=Value(0),
                    ),
                    When(
                        prefix_filter,
                        then=Value(1),
                    ),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )
            .order_by(
                "square_search_rank",
                "-published_at",
                "-id",
            )
        )

    @staticmethod
    def normalize_query(
        value: str | None,
    ) -> str:
        return str(
            value or ""
        ).strip()

    @staticmethod
    def _sort_key(
        obj,
    ) -> tuple:
        published_at = getattr(
            obj,
            "published_at",
            None,
        )

        published_timestamp = (
            published_at.timestamp()
            if published_at is not None
            else 0.0
        )

        raw_rank = getattr(
            obj,
            "square_search_rank",
            None,
        )

        search_rank = (
            int(raw_rank)
            if raw_rank is not None
            else 2
        )

        return (
            search_rank,
            -published_timestamp,
            str(
                getattr(
                    obj,
                    "square_kind",
                    "",
                )
                or ""
            ),
            -int(
                getattr(
                    obj,
                    "id",
                    0,
                )
                or 0
            ),
        )