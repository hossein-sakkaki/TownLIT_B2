# apps/core/streams/sources.py

from apps.core.streams.registry import (
    StreamContentSource,
    register_stream_source,
)

from apps.core.streams.constants import (
    STREAM_KIND_MOMENT,
    STREAM_KIND_TESTIMONY,
    STREAM_KIND_PRAY,
)

from apps.posts.models.moment import Moment
from apps.posts.models.testimony import Testimony
from apps.posts.models.pray import Prayer


# -------------------------------------------------
# Moment
# -------------------------------------------------

register_stream_source(
    source=StreamContentSource(
        model=Moment,
        kind=STREAM_KIND_MOMENT,
        media_fields=["video", "image"],
        requires_conversion=True,
        owner_user_lookup="content_type/object_id",
    )
)


# -------------------------------------------------
# Testimony
# -------------------------------------------------

register_stream_source(
    source=StreamContentSource(
        model=Testimony,
        kind=STREAM_KIND_TESTIMONY,
        media_fields=["video", "audio", "written"],
        requires_conversion=True,
        owner_user_lookup="content_type/object_id",
    )
)


# -------------------------------------------------
# Prayer
# -------------------------------------------------

register_stream_source(
    source=StreamContentSource(
        model=Prayer,
        kind=STREAM_KIND_PRAY,
        media_fields=["video", "image"],
        requires_conversion=True,
        owner_user_lookup="content_type/object_id",
    )
)


# apps/core/streams/views.py

from django.shortcuts import get_object_or_404

from rest_framework import viewsets
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
            return Response({
                "next": None,
                "results": [],
                "limit_reached": True,
                "extension": context.extension,
                "can_continue": False,
            })

        source = get_stream_source(context.kind)
        if not source:
            return Response({"detail": "Unsupported stream kind"}, status=400)

        seed_qs = StreamQuery.seed_queryset(
            model=source.model,
            viewer=context.viewer,
        )

        seed = get_object_or_404(
            seed_qs,
            id=context.seed_id,
        )

        subtype = resolve_stream_subtype(seed)
        if not subtype:
            return Response({"detail": "Unsupported stream subtype"}, status=400)

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

        results = [
            item
            for item in serializer.data
            if item is not None
        ]

        return Response({
            "next": page.next_cursor,
            "results": results,
            "kind": page.kind,
            "subtype": page.subtype,
            "scope": page.scope,
            "mode": page.mode,
            "extension": page.extension,
            "can_continue": context.extension + 1 < STREAM_MAX_EXTENSIONS,
            "limit_reached": False,
        })

    def _validate_context(self, context):
        """
        Validate stream context.
        """

        if not context.kind or not context.seed_id:
            return Response({"detail": "Invalid stream request"}, status=400)

        if context.kind not in STREAM_KINDS:
            return Response({"detail": "Invalid kind"}, status=400)

        if context.scope not in STREAM_SCOPES:
            return Response({"detail": "Invalid scope"}, status=400)

        if context.mode not in STREAM_MODES:
            return Response({"detail": "Invalid mode"}, status=400)

        return None
    
    
    
