# apps/core/square/search_views.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.square.search import (
    SquareContentSearch,
)
from apps.core.square.serializers import (
    SquareItemSerializer,
)


SQUARE_SEARCH_PAGE_SIZE = 20


class SquareContentSearchPagination(
    PageNumberPagination
):
    page_size = SQUARE_SEARCH_PAGE_SIZE
    page_size_query_param = None
    max_page_size = SQUARE_SEARCH_PAGE_SIZE


class SquareContentSearchView(APIView):
    """
    Search visible Square content.

    Current provider:
    - Content

    Future hashtag and mention semantics must remain separate from
    model-specific relationship tags until their domain is defined.
    """

    permission_classes = [
        permissions.AllowAny,
    ]

    def get(
        self,
        request,
    ):
        viewer = (
            request.user
            if request.user.is_authenticated
            else None
        )

        query = request.query_params.get(
            "q",
            "",
        )

        items = SquareContentSearch.search(
            viewer=viewer,
            query=query,
        )

        paginator = (
            SquareContentSearchPagination()
        )

        page = paginator.paginate_queryset(
            items,
            request,
            view=self,
        )

        serializer = SquareItemSerializer(
            page,
            many=True,
            context={
                "request": request,
            },
        )

        results = [
            item
            for item in serializer.data
            if item is not None
        ]

        return paginator.get_paginated_response(
            results
        )