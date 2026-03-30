# apps/core/square/views.py

import logging
from urllib.parse import unquote, urlencode, urlparse, parse_qs

from django.db.models import F, Q
from django.utils.dateparse import parse_datetime

from rest_framework import viewsets, permissions
from rest_framework.response import Response

from apps.core.square.query import SquareQuery
from apps.core.square.engines import SquareEngine
from apps.core.square.serializers import SquareItemSerializer
from apps.core.square.constants import SQUARE_KIND_ALL, SQUARE_KIND_FRIENDS
from apps.core.pagination import FeedCursorPagination

logger = logging.getLogger(__name__)


class SquareViewSet(viewsets.ViewSet):
    """
    Square feed endpoints.

    Notes:
    - Engines annotate only (NO ordering).
    - ViewSet applies cursor-safe ordering per mode.
    - For kind=all: we merge multiple sources in Python.
    - Serializer may gate items (return None) => we filter them out.
    """

    permission_classes = [permissions.AllowAny]
    pagination_class = FeedCursorPagination
    pagination_page_size = 12

    # ------------------------------------------------------------------
    # Score helpers
    # ------------------------------------------------------------------
    def _score_of(self, obj, *, mode: str | None, viewer) -> float:
        """
        Return the correct score for the requested mode.
        Fallback to 0 when annotation is missing.
        """
        if mode == SquareEngine.MODE_TRENDING:
            return float(getattr(obj, "trending_score", 0) or 0)

        if mode == SquareEngine.MODE_FOR_YOU and viewer:
            return float(getattr(obj, "personalized_trending_score", 0) or 0)

        if mode == SquareEngine.MODE_RECENT:
            return float(getattr(obj, "rank_score", 0) or 0)

        return float(getattr(obj, "hybrid_score", 0) or 0)

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------
    def _cursor_token_only(self, cursor: str | None) -> str | None:
        """
        Accept either:
        - token: "s=...&p=...&id=..."
        - full URL containing ?cursor=...
        Returns token only (or None).
        """
        if not cursor:
            return None

        cursor = cursor.strip()

        if cursor.startswith("http://") or cursor.startswith("https://"):
            try:
                q = parse_qs(urlparse(cursor).query)
                val = q.get("cursor", [None])[0]
                return val or None
            except Exception:
                return None

        return cursor

    def _parse_cursor_parts(self, cursor: str | None) -> dict:
        """
        Parse cursor token into parts:
          s=<score>&p=<iso_datetime>&id=<int>
        """
        token = self._cursor_token_only(cursor)
        if not token:
            return {}

        token = unquote(token)

        parts = {}
        for chunk in token.split("&"):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                parts[k] = v

        return parts

    def _apply_cursor_boundary_multi_source(self, objs, cursor: str | None, *, mode: str | None, viewer):
        """
        Apply an in-memory cursor boundary for merged multi-source results.

        Order tuple:
          (score DESC, published_at DESC, id DESC)

        So the next page must contain only items strictly smaller than:
          (cursor_score, cursor_published_at, cursor_id)
        """
        parts = self._parse_cursor_parts(cursor)
        if not parts:
            return objs

        s_raw = parts.get("s")
        p_raw = parts.get("p")
        id_raw = parts.get("id")

        if s_raw is None or not p_raw or not id_raw:
            return objs

        try:
            cursor_score = float(s_raw)
            cursor_published_at = parse_datetime(p_raw)
            cursor_id = int(id_raw)
        except Exception:
            return objs

        if cursor_published_at is None:
            return objs

        filtered = []
        for obj in objs:
            obj_score = self._score_of(obj, mode=mode, viewer=viewer)
            obj_published_at = getattr(obj, "published_at", None)
            obj_id = getattr(obj, "id", None)

            if obj_published_at is None or obj_id is None:
                continue

            # Keep items strictly after the cursor in DESC ordering.
            if obj_score < cursor_score:
                filtered.append(obj)
                continue

            if obj_score == cursor_score:
                if obj_published_at < cursor_published_at:
                    filtered.append(obj)
                    continue

                if obj_published_at == cursor_published_at and obj_id < cursor_id:
                    filtered.append(obj)
                    continue

        return filtered

    def _build_next_link(self, request, *, last_obj, mode: str | None, viewer):
        """
        Build the next cursor URL using the SAME ordering tuple.
        """
        token = urlencode(
            {
                "s": str(self._score_of(last_obj, mode=mode, viewer=viewer)),
                "p": last_obj.published_at.isoformat(),
                "id": str(last_obj.id),
            }
        )

        qd = request.query_params.copy()
        qd["cursor"] = token
        return request.build_absolute_uri(f"{request.path}?{qd.urlencode()}")

    def _order_qs_by_mode(self, qs, *, mode: str | None, viewer):
        """
        Apply cursor-safe ordering depending on mode.
        Returns: (ordered_qs, score_field_name)
        """
        if mode == SquareEngine.MODE_TRENDING:
            return (
                qs.order_by(
                    F("trending_score").desc(nulls_last=True),
                    F("published_at").desc(),
                    F("id").desc(),
                ),
                "trending_score",
            )

        if mode == SquareEngine.MODE_FOR_YOU and viewer:
            return (
                qs.order_by(
                    F("personalized_trending_score").desc(nulls_last=True),
                    F("published_at").desc(),
                    F("id").desc(),
                ),
                "personalized_trending_score",
            )

        if mode == SquareEngine.MODE_RECENT:
            return (
                qs.order_by(
                    F("rank_score").desc(nulls_last=True),
                    F("published_at").desc(),
                    F("id").desc(),
                ),
                "rank_score",
            )

        return (
            qs.order_by(
                F("hybrid_score").desc(nulls_last=True),
                F("published_at").desc(),
                F("id").desc(),
            ),
            "hybrid_score",
        )

    # ------------------------------------------------------------------
    # Main endpoint
    # ------------------------------------------------------------------
    def list(self, request):
        viewer = request.user if request.user.is_authenticated else None

        kind = request.query_params.get("kind", SQUARE_KIND_ALL)
        mode = request.query_params.get("mode")  # recent | trending | for_you | None
        cursor = request.query_params.get("cursor")

        logger.info(
            "[Square] request kind=%s mode=%s auth=%s user_id=%s",
            kind,
            mode or "hybrid",
            bool(viewer),
            getattr(viewer, "id", None),
        )

        # -------------------------------------------------
        # 1) Build source querysets
        # -------------------------------------------------
        querysets = SquareQuery.build(viewer=viewer, kind=kind)

        logger.info(
            "[Square] built querysets kind=%s sources=%s",
            kind,
            len(querysets),
        )

        if not querysets:
            logger.info("[Square] empty querysets -> return empty")
            return Response({"next": None, "results": []})

        # -------------------------------------------------
        # 2) ALL + FRIENDS => merge multiple sources
        # -------------------------------------------------
        if kind in (SQUARE_KIND_ALL, SQUARE_KIND_FRIENDS):
            page_size = int(getattr(self, "pagination_page_size", 12))

            # Bigger fetch window for production skew.
            per_source_limit = page_size * 40

            merged_objs = []

            try:
                for src_qs in querysets:
                    model_name = getattr(
                        getattr(src_qs, "model", None),
                        "__name__",
                        "UnknownModel",
                    )

                    logger.info(
                        "[Square] merge source=%s pre_engine_count=%s",
                        model_name,
                        src_qs.count(),
                    )

                    qs = SquareEngine.apply(
                        queryset=src_qs,
                        mode=mode,
                        viewer=viewer,
                    )

                    qs, score_field = self._order_qs_by_mode(
                        qs,
                        mode=mode,
                        viewer=viewer,
                    )

                    logger.info(
                        "[Square] source=%s ordered_by=%s",
                        model_name,
                        score_field,
                    )

                    merged_objs.extend(list(qs[:per_source_limit]))

                # Global stable sort using the SAME tuple as cursor.
                merged_objs.sort(
                    key=lambda o: (
                        self._score_of(o, mode=mode, viewer=viewer),
                        getattr(o, "published_at", None),
                        getattr(o, "id", None),
                    ),
                    reverse=True,
                )

                # Apply cursor AFTER merge using the SAME tuple.
                merged_objs = self._apply_cursor_boundary_multi_source(
                    merged_objs,
                    cursor,
                    mode=mode,
                    viewer=viewer,
                )

                logger.info(
                    "[Square] MERGE kind=%s merged=%s mode=%s viewer=%s",
                    kind,
                    len(merged_objs),
                    mode or "hybrid",
                    bool(viewer),
                )

                for obj in merged_objs[:10]:
                    logger.info(
                        "[SquareDebug] top obj id=%s kind=%s score=%s pub=%s",
                        getattr(obj, "id", None),
                        getattr(obj, "square_kind", None),
                        self._score_of(obj, mode=mode, viewer=viewer),
                        getattr(obj, "published_at", None),
                    )

            except Exception:
                logger.exception("[Square] MERGE failed")
                raise

            # Bigger candidate window to survive serializer gating.
            candidate_window = merged_objs[: (page_size * 12)]

            serializer = SquareItemSerializer(
                candidate_window,
                many=True,
                context={"request": request},
            )

            results = []
            last_obj_for_cursor = None

            for obj, rep in zip(candidate_window, serializer.data):
                if rep is None:
                    continue

                results.append(rep)
                last_obj_for_cursor = obj

                if len(results) >= page_size:
                    break

            next_link = None
            if len(results) >= page_size and last_obj_for_cursor is not None:
                next_link = self._build_next_link(
                    request,
                    last_obj=last_obj_for_cursor,
                    mode=mode,
                    viewer=viewer,
                )

            logger.info(
                "[Square] final merged results=%s next=%s",
                len(results),
                bool(next_link),
            )

            return Response({"next": next_link, "results": results})

        # -------------------------------------------------
        # 3) Non-ALL tabs => single source
        # -------------------------------------------------
        base_qs = querysets[0]

        try:
            ranked_qs = SquareEngine.apply(
                queryset=base_qs,
                mode=mode,
                viewer=viewer,
            )

            ranked_qs, score_field = self._order_qs_by_mode(
                ranked_qs,
                mode=mode,
                viewer=viewer,
            )

            logger.info(
                "[Square] kind=%s mode=%s viewer=%s score=%s",
                kind,
                mode or "hybrid",
                bool(viewer),
                score_field,
            )

        except Exception:
            logger.exception("[Square] engine failed")
            raise

        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(ranked_qs, request, view=self)
        except Exception:
            logger.exception("[Square] pagination failed")
            raise

        serializer = SquareItemSerializer(
            page,
            many=True,
            context={"request": request},
        )
        data = [item for item in serializer.data if item is not None]

        gated_none_count = (
            len(serializer.data) - len(data)
        ) if serializer.data else 0

        logger.info(
            "[Square] page=%s returned=%s gated=%s next=%s",
            len(page or []),
            len(data or []),
            gated_none_count,
            bool(paginator.get_next_link()),
        )

        return paginator.get_paginated_response(data)