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
    - For kind=all: we MERGE multiple sources in Python (no UNION yet).
    - Serializer may gate items (return None) => we filter them out.
    """

    permission_classes = [permissions.AllowAny]
    pagination_class = FeedCursorPagination
    pagination_page_size = 12

    # ------------------------------------------------------------------
    # Cursor helpers (for multi-source merge "all")
    # ------------------------------------------------------------------
    def _cursor_token_only(self, cursor: str | None) -> str | None:
        """
        Accept either:
        - token: "p=...&id=..."
        - full URL containing ?cursor=...
        Returns token only (or None).
        """
        if not cursor:
            return None

        cursor = cursor.strip()

        # If full URL is passed, extract its cursor param
        if cursor.startswith("http://") or cursor.startswith("https://"):
            try:
                q = parse_qs(urlparse(cursor).query)
                val = q.get("cursor", [None])[0]
                return val or None
            except Exception:
                return None

        return cursor

    def _apply_cursor_boundary(self, qs, cursor: str | None):
        """
        Cursor boundary for multi-source merge.

        Cursor token format:
          "p=<iso_datetime>&id=<int>"
        (URL-encoded is ok)
        """
        token = self._cursor_token_only(cursor)
        if not token:
            return qs

        # token could be urlencoded "p=...&id=..."
        token = unquote(token)

        parts = {}
        for chunk in token.split("&"):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                parts[k] = v

        p_raw = parts.get("p")
        id_raw = parts.get("id")
        if not p_raw or not id_raw:
            return qs

        try:
            p = parse_datetime(p_raw)
            last_id = int(id_raw)
        except Exception:
            return qs

        if not p:
            return qs

        # (published_at, id) < (p, last_id)
        return qs.filter(
            Q(published_at__lt=p) | Q(published_at=p, id__lt=last_id)
        )

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

        # default: hybrid
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
        # 2) ALL + FRIENDS => merge multiple sources (no UNION)
        # -------------------------------------------------
        if kind in (SQUARE_KIND_ALL, SQUARE_KIND_FRIENDS):
            page_size = int(getattr(self, "pagination_page_size", 12))

            # Over-fetch to survive serializer gating / duplicates
            per_source_limit = page_size * 20

            merged_objs = []

            try:
                for src_qs in querysets:
                    model_name = getattr(getattr(src_qs, "model", None), "__name__", "UnknownModel")
                    logger.info("[Square] merge source=%s pre_engine_count=%s", model_name, src_qs.count())
                    # annotate by engine (no ordering inside engines)
                    qs = SquareEngine.apply(
                        queryset=src_qs,
                        mode=mode,
                        viewer=viewer,
                    )


                    # apply cursor boundary for this source (published_at/id)
                    qs = self._apply_cursor_boundary(qs, cursor)

                    # apply ordering based on mode
                    qs, score_field = self._order_qs_by_mode(
                        qs,
                        mode=mode,
                        viewer=viewer,
                    )

                    # take a slice from each source
                    merged_objs.extend(list(qs[:per_source_limit]))

                # global merge ordering (simple + stable)
                def _score_of(o):
                    return (
                        getattr(o, "personalized_trending_score", None)
                        or getattr(o, "trending_score", None)
                        or getattr(o, "rank_score", None)
                        or getattr(o, "hybrid_score", None)
                        or 0
                    )

                merged_objs.sort(
                    key=lambda o: (_score_of(o), o.published_at, o.id),
                    reverse=True,
                )

                logger.info(
                    "[Square] MERGE kind=%s merged=%s mode=%s viewer=%s",
                    kind,
                    len(merged_objs),
                    mode or "hybrid",
                    bool(viewer),
                )

            except Exception:
                logger.exception("[Square] MERGE failed")
                raise

            # Serialize a larger candidate window; keep first page_size real items
            candidate_window = merged_objs[: (page_size * 6)]
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
                token = urlencode(
                    {
                        "p": last_obj_for_cursor.published_at.isoformat(),
                        "id": str(last_obj_for_cursor.id),
                    }
                )

                qd = request.query_params.copy()
                qd["cursor"] = token
                next_link = request.build_absolute_uri(f"{request.path}?{qd.urlencode()}")

            return Response({"next": next_link, "results": results})

        # -------------------------------------------------
        # 3) Non-ALL tabs => single source (cursor pagination)
        # -------------------------------------------------
        base_qs = querysets[0]  # single source for moment/testimony tabs

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

        serializer = SquareItemSerializer(page, many=True, context={"request": request})
        data = [item for item in serializer.data if item is not None]

        gated_none_count = (len(serializer.data) - len(data)) if serializer.data else 0
        logger.info(
            "[Square] page=%s returned=%s gated=%s next=%s",
            len(page or []),
            len(data or []),
            gated_none_count,
            bool(paginator.get_next_link()),
        )

        return paginator.get_paginated_response(data)
