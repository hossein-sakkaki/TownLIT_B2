# apps/core/streams/views.py

from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.streams.constants import (
    STREAM_KINDS,
    STREAM_SCOPES,
    STREAM_MODES,
    STREAM_SCOPE_SQUARE,
    STREAM_SQUARE_MAX_EXTENSIONS,
    STREAM_SQUARE_PAGE_SIZE,
    STREAM_LIMITED_EXTENSION_SCOPES,
)
from apps.core.streams.context import parse_stream_context
from apps.core.streams.engine import StreamEngine
from apps.core.streams.query import StreamQuery
from apps.core.streams.registry import get_stream_source
from apps.core.streams.resolvers import resolve_stream_subtype
from apps.core.streams.serializers import StreamItemSerializer


class StreamViewSet(viewsets.ViewSet):
    """
    Universal content stream endpoint.

    Important policy:
    - Square streams are intentionally limited.
    - Profile/owner/global streams are not blocked by the Square anti-addiction limit.
    """

    permission_classes = [AllowAny]

    def list(self, request):
        context = parse_stream_context(request)

        validation_error = self._validate_context(context)
        if validation_error:
            return validation_error

        if self._is_square_limit_reached(context):
            return Response(
                {
                    "next": None,
                    "results": [],
                    "kind": context.kind,
                    "subtype": None,
                    "scope": context.scope,
                    "mode": context.mode,
                    "extension": context.extension,
                    "can_continue": False,
                    "limit_reached": True,
                    "policy": self._policy_payload(context),
                },
                status=status.HTTP_200_OK,
            )

        source = get_stream_source(context.kind)
        if not source:
            return Response(
                {"detail": "Unsupported stream kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seed_qs = StreamQuery.seed_queryset(
            model=source.model,
            viewer=context.viewer,
            scope=context.scope,
        )

        seed = get_object_or_404(
            seed_qs,
            id=context.seed_id,
        )

        subtype = resolve_stream_subtype(seed)
        if not subtype:
            return Response(
                {"detail": "Unsupported stream subtype"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page = StreamEngine.build_page(
            context=context,
            source=source,
            seed=seed,
            subtype=subtype,
        )

        serializer = StreamItemSerializer(
            page.items,
            many=True,
            context={"request": request},
        )

        results = []

        for item in serializer.data:
            if not item:
                continue

            payload = item.get("payload") if isinstance(item, dict) else None
            if payload is None:
                continue

            results.append(item)

        return Response(
            {
                "next": self._resolved_next_cursor(
                    context=context,
                    next_cursor=page.next_cursor,
                ),
                "results": results,
                "kind": page.kind,
                "subtype": page.subtype,
                "scope": page.scope,
                "mode": page.mode,
                "extension": page.extension,
                "can_continue": self._can_continue(context),
                "limit_reached": False,
                "policy": self._policy_payload(context),
            },
            status=status.HTTP_200_OK,
        )

    def _validate_context(self, context):
        """
        Validate stream context.
        """

        if not context.kind or not context.seed_id:
            return Response(
                {"detail": "Invalid stream request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if context.kind not in STREAM_KINDS:
            return Response(
                {"detail": "Invalid kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if context.scope not in STREAM_SCOPES:
            return Response(
                {"detail": "Invalid scope"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if context.mode not in STREAM_MODES:
            return Response(
                {"detail": "Invalid mode"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return None

    def _is_limited_extension_scope(self, context) -> bool:
        return context.scope in STREAM_LIMITED_EXTENSION_SCOPES

    def _is_square_limit_reached(self, context) -> bool:
        if not self._is_limited_extension_scope(context):
            return False

        current_extension = max(
            int(context.extension or 0),
            0,
        )

        return current_extension >= STREAM_SQUARE_MAX_EXTENSIONS

    def _can_continue(self, context) -> bool:
        """
        Limited extension scopes allow exactly STREAM_SQUARE_MAX_EXTENSIONS batches.

        With STREAM_SQUARE_MAX_EXTENSIONS = 3:
        extension=0 -> can continue to extension=1
        extension=1 -> can continue to extension=2
        extension=2 -> stop after this batch
        """

        if not self._is_limited_extension_scope(context):
            return False

        current_extension = max(
            int(context.extension or 0),
            0,
        )

        last_allowed_extension = STREAM_SQUARE_MAX_EXTENSIONS - 1

        return current_extension < last_allowed_extension

    def _resolved_next_cursor(
        self,
        *,
        context,
        next_cursor,
    ):
        """
        Limited extension scopes advance by explicit extensions, not automatic
        cursor pagination.

        Non-limited scopes can keep cursor pagination.
        """

        if self._is_limited_extension_scope(context):
            return None

        return next_cursor
    
    def _policy_payload(self, context) -> dict:
        """
        Expose stream policy to clients so UI does not hard-code limits.
        """

        if self._is_limited_extension_scope(context):
            return {
                "scope": context.scope,
                "is_limited": True,
                "batch_size": STREAM_SQUARE_PAGE_SIZE,
                "batch_count": STREAM_SQUARE_MAX_EXTENSIONS,
                "max_items": STREAM_SQUARE_PAGE_SIZE * STREAM_SQUARE_MAX_EXTENSIONS,
            }

        return {
            "scope": context.scope,
            "is_limited": False,
            "batch_size": None,
            "batch_count": None,
            "max_items": None,
        }