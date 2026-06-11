# apps/core/streams/views.py

from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.streams.constants import (
    STREAM_KINDS,
    STREAM_SCOPES,
    STREAM_MODES,
    STREAM_MAX_EXTENSIONS,
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
    """

    permission_classes = [AllowAny]

    def list(self, request):
        context = parse_stream_context(request)

        validation_error = self._validate_context(context)
        if validation_error:
            return validation_error

        if context.extension >= STREAM_MAX_EXTENSIONS:
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
                "next": page.next_cursor,
                "results": results,
                "kind": page.kind,
                "subtype": page.subtype,
                "scope": page.scope,
                "mode": page.mode,
                "extension": page.extension,
                "can_continue": context.extension + 1 < STREAM_MAX_EXTENSIONS,
                "limit_reached": False,
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
    
    
