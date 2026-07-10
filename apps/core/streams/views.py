# apps/core/streams/views.py

from time import perf_counter

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.streams.constants import (
    STREAM_KINDS,
    STREAM_SCOPES,
    STREAM_MODES,
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


def _stream_perf_enabled() -> bool:
    return bool(
        getattr(
            settings,
            "STREAM_PERF_LOGS_ENABLED",
            getattr(settings, "DEBUG", False),
        )
    )


def _stream_mark(name: str, **kwargs) -> None:
    if not _stream_perf_enabled():
        return

    suffix = " ".join(
        f"{key}={value}"
        for key, value in kwargs.items()
    )

def _stream_time(name: str, started_at: float, **kwargs) -> None:
    if not _stream_perf_enabled():
        return

    elapsed_ms = int((perf_counter() - started_at) * 1000)

    suffix = " ".join(
        f"{key}={value}"
        for key, value in kwargs.items()
    )


class StreamViewSet(viewsets.ViewSet):
    """
    Universal content stream endpoint.

    Important policy:
    - Square streams are intentionally limited.
    - Profile/owner/global streams are not blocked by the Square anti-addiction limit.
    """

    permission_classes = [AllowAny]

    def list(self, request):
        total_start = perf_counter()

        context_start = perf_counter()
        context = parse_stream_context(request)

        _stream_time(
            "Stream.view.context",
            context_start,
            kind=context.kind,
            seed=context.seed_id,
            scope=context.scope,
            mode=context.mode,
            ext=context.extension,
            cursor=bool(context.cursor),
            authed=bool(context.viewer),
        )

        validation_start = perf_counter()
        validation_error = self._validate_context(context)

        _stream_time(
            "Stream.view.validate",
            validation_start,
            ok=not bool(validation_error),
        )

        if validation_error:
            _stream_time(
                "Stream.view.total",
                total_start,
                status=400,
                reason="validation",
            )
            return validation_error

        if self._is_square_limit_reached(context):
            _stream_time(
                "Stream.view.total",
                total_start,
                status=200,
                reason="limitReached",
                ext=context.extension,
            )

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

        source_start = perf_counter()
        source = get_stream_source(context.kind)

        _stream_time(
            "Stream.view.source",
            source_start,
            found=bool(source),
            kind=context.kind,
        )

        if not source:
            _stream_time(
                "Stream.view.total",
                total_start,
                status=400,
                reason="unsupportedKind",
            )

            return Response(
                {"detail": "Unsupported stream kind"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        seed_qs_start = perf_counter()

        seed_qs = StreamQuery.seed_queryset(
            model=source.model,
            viewer=context.viewer,
            scope=context.scope,
        )

        _stream_time(
            "Stream.view.seedQuery.build",
            seed_qs_start,
            model=source.model.__name__,
            scope=context.scope,
        )

        seed_start = perf_counter()

        seed = get_object_or_404(
            seed_qs,
            id=context.seed_id,
        )

        _stream_time(
            "Stream.view.seed.fetch",
            seed_start,
            seed=context.seed_id,
            model=source.model.__name__,
        )

        subtype_start = perf_counter()
        subtype = resolve_stream_subtype(seed)

        _stream_time(
            "Stream.view.subtype",
            subtype_start,
            subtype=subtype,
        )

        if not subtype:
            _stream_time(
                "Stream.view.total",
                total_start,
                status=400,
                reason="unsupportedSubtype",
            )

            return Response(
                {"detail": "Unsupported stream subtype"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        engine_start = perf_counter()

        page = StreamEngine.build_page(
            context=context,
            source=source,
            seed=seed,
            subtype=subtype,
        )

        _stream_time(
            "Stream.view.engine",
            engine_start,
            rawItems=len(page.items),
            nextCursor=bool(page.next_cursor),
            ext=page.extension,
        )

        serializer_start = perf_counter()

        serializer = StreamItemSerializer(
            page.items,
            many=True,
            context={"request": request},
        )

        serialized_data = serializer.data

        _stream_time(
            "Stream.view.serializer",
            serializer_start,
            rawItems=len(page.items),
            serialized=len(serialized_data),
        )

        filter_start = perf_counter()

        results = []

        for item in serialized_data:
            if not item:
                continue

            payload = item.get("payload") if isinstance(item, dict) else None
            if payload is None:
                continue

            results.append(item)

        _stream_time(
            "Stream.view.results.filter",
            filter_start,
            serialized=len(serialized_data),
            results=len(results),
        )

        response_payload_start = perf_counter()

        payload = {
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
            "can_continue": self._can_continue_for_results(
                context=context,
                results_count=len(results),
            ),
            "limit_reached": False,
            "policy": self._policy_payload(context),
        }

        _stream_time(
            "Stream.view.payload.build",
            response_payload_start,
            results=len(results),
        )

        _stream_time(
            "Stream.view.total",
            total_start,
            status=200,
            results=len(results),
            canContinue=payload["can_continue"],
            scope=context.scope,
            mode=context.mode,
            ext=context.extension,
        )

        return Response(
            payload,
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

    def _can_continue_for_results(
        self,
        *,
        context,
        results_count: int,
    ) -> bool:
        """
        Limited extension streams can continue only when:
        - policy still allows another extension
        - current batch is full

        If the backend returns a partial batch, there is no reliable reason to
        show Continue again.
        """

        if not self._can_continue(context):
            return False

        if not self._is_limited_extension_scope(context):
            return False

        return int(results_count or 0) >= STREAM_SQUARE_PAGE_SIZE

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