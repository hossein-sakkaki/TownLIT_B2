# apps/core/square/stream/views.py

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.core.square.registry import get_square_source
from apps.core.square.stream.constants import (
    STREAM_PAGE_SIZE,
    STREAM_MAX_EXTENSIONS,
)
from apps.core.square.stream.query import SquareStreamQuery
from apps.core.square.stream.engine import SquareStreamEngine
from apps.core.square.stream.serializers import SquareStreamItemSerializer
from apps.core.square.stream.resolvers import resolve_stream_subtype
from apps.core.square.stream.dto import StreamItem

from random import shuffle
from django.db.models import Q

from apps.core.square.stream.constants import (
    STREAM_PAGE_SIZE,
    STREAM_MAX_EXTENSIONS,
    STREAM_SUBTYPE_VIDEO,
    STREAM_SUBTYPE_AUDIO,
    STREAM_SUBTYPE_WRITTEN,
)

class SquareStreamViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        viewer = request.user if request.user.is_authenticated else None

        kind = request.query_params.get("kind")
        seed_id = request.query_params.get("seed_id")
        cursor_raw = request.query_params.get("cursor")
        extension = int(request.query_params.get("ext", 0))

        # -------------------------------------------------
        # Basic validation
        # -------------------------------------------------
        if not kind or not seed_id:
            return Response({"detail": "Invalid stream request"}, status=400)

        if extension >= STREAM_MAX_EXTENSIONS:
            return Response({
                "next": None,
                "results": [],
                "limit_reached": True,
            })

        source = get_square_source(kind)
        if not source:
            return Response({"detail": "Invalid kind"}, status=400)

        model = source.model
        seed = get_object_or_404(model, id=seed_id)

        subtype = resolve_stream_subtype(seed)
        if not subtype:
            return Response({"detail": "Unsupported stream subtype"}, status=400)

        # -------------------------------------------------
        # Cursor parsing
        # -------------------------------------------------
        cursor = None
        if cursor_raw:
            try:
                p, i = cursor_raw.split("|")
                cursor = (parse_datetime(p), int(i))
            except Exception:
                cursor = None

        # -------------------------------------------------
        # Base queryset (domain rules only)
        # -------------------------------------------------
        base_qs = SquareStreamQuery.build(
            model=model,
            viewer=viewer,
            subtype=subtype,
            seed=seed,
        )

        # -------------------------------------------------
        # 🔢 Effective limit (keep TOTAL = 5)
        # -------------------------------------------------
        effective_limit = STREAM_PAGE_SIZE - (1 if not cursor else 0)

        # -------------------------------------------------
        # Tier-based relatedness engine
        # - Moments: same-subtype only (current behavior)
        # - Testimonies: fill shortage using other subtypes
        # -------------------------------------------------
        used_ids: set[int] = set()

        # (Extra safety: avoid any chance of seed duplication)
        used_ids.add(seed.id)

        stream_items: list = []

        if kind == "testimony":
            # ---------------------------------------------
            # 1) Build subtype fallback pool (seed first)
            # ---------------------------------------------
            all_testimony_subtypes = [
                STREAM_SUBTYPE_VIDEO,
                STREAM_SUBTYPE_AUDIO,
                STREAM_SUBTYPE_WRITTEN,
            ]

            fallback = [s for s in all_testimony_subtypes if s != subtype]
            shuffle(fallback)  # "not ordered" as you requested
            subtype_pool = [subtype] + fallback

            remaining = effective_limit

            for st in subtype_pool:
                if remaining <= 0:
                    break

                qs_for_st = SquareStreamQuery.build(
                    model=model,
                    viewer=viewer,
                    subtype=st,
                    seed=seed,
                )

                # optional: reduce DB work by excluding used ids early
                if used_ids:
                    qs_for_st = qs_for_st.exclude(id__in=used_ids)

                batch = SquareStreamEngine.apply(
                    queryset=qs_for_st,
                    seed=seed,
                    kind=kind,
                    viewer=viewer,
                    cursor=cursor,
                    limit=remaining,
                    used_ids=used_ids,
                )

                stream_items.extend(batch)
                remaining = effective_limit - len(stream_items)

        else:
            # ---------------------------------------------
            # Moments: keep current same-subtype logic
            # ---------------------------------------------
            stream_items = SquareStreamEngine.apply(
                queryset=base_qs,
                seed=seed,
                kind=kind,
                viewer=viewer,
                cursor=cursor,
                limit=effective_limit,
                used_ids=used_ids,
            )

        # -------------------------------------------------
        # Build DTO items
        # -------------------------------------------------
        items: list[StreamItem] = []

        # Seed only on first page
        if not cursor:
            items.append(StreamItem(kind=kind, obj=seed))

        for obj in stream_items:
            items.append(StreamItem(kind=kind, obj=obj))


        # -------------------------------------------------
        # Empty-safe response
        # -------------------------------------------------
        if not items:
            return Response({
                "next": None,
                "results": [],
                "subtype": subtype,
                "extension": extension,
                "can_continue": extension + 1 < STREAM_MAX_EXTENSIONS,
            })

        serializer = SquareStreamItemSerializer(
            items,
            many=True,
            context={"request": request},
        )

        last_obj = items[-1].obj
        next_cursor = f"{last_obj.published_at.isoformat()}|{last_obj.id}"

        return Response({
            "next": next_cursor,
            "results": serializer.data,
            "subtype": subtype,
            "extension": extension,
            "can_continue": extension + 1 < STREAM_MAX_EXTENSIONS,
        })
