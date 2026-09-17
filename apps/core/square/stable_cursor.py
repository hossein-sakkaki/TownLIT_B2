# apps/core/square/stable_cursor.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from urllib.parse import (
    parse_qs,
    urlparse,
)

from django.core import signing
from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_datetime

from apps.core.square.engines import SquareEngine
from apps.core.square.query import SquareQuery
from apps.core.square.registry import get_square_sources
from apps.core.square.serializers import SquareItemSerializer


SQUARE_STABLE_CURSOR_VERSION = 2

SQUARE_STABLE_CURSOR_PREFIX = "sqv2."
SQUARE_STABLE_CURSOR_SALT = (
    "townlit.square.stable-feed.v2"
)

# Each source contributes a stable chronological candidate window.
SQUARE_STABLE_INITIAL_SCAN_PER_SOURCE = 200

# Refill keeps the rolling personalization window healthy.
SQUARE_STABLE_REFILL_MIN_PER_SOURCE = 20

# Avoid serializing the whole candidate buffer just to produce 20 items.
SQUARE_STABLE_SERIALIZATION_CHUNK = 60


class SquareStableCursorError(ValueError):
    pass


@dataclass(frozen=True)
class SquareStableSourceBoundary:
    published_at: datetime
    object_id: int


@dataclass
class SquareStableCursorState:
    viewer_key: str
    kind: str
    mode: str

    source_kinds: list[str] = field(
        default_factory=list
    )

    remaining_ids: dict[str, list[int]] = field(
        default_factory=dict
    )

    boundaries: dict[
        str,
        SquareStableSourceBoundary,
    ] = field(
        default_factory=dict
    )

    exhausted_kinds: set[str] = field(
        default_factory=set
    )


@dataclass(frozen=True)
class SquareStableFeedPage:
    results: list[dict]
    next_cursor: str | None


class SquareStableCursorCodec:
    @classmethod
    def is_stable_cursor(
        cls,
        raw_cursor: str | None,
    ) -> bool:
        token = cls._cursor_token_only(
            raw_cursor
        )

        return bool(
            token
            and token.startswith(
                SQUARE_STABLE_CURSOR_PREFIX
            )
        )

    @classmethod
    def encode(
        cls,
        state: SquareStableCursorState,
    ) -> str:
        payload = {
            "v": SQUARE_STABLE_CURSOR_VERSION,
            "u": state.viewer_key,
            "k": state.kind,
            "m": state.mode,
            "s": state.source_kinds,
            "r": state.remaining_ids,
            "b": {
                kind: [
                    boundary.published_at.isoformat(),
                    boundary.object_id,
                ]
                for kind, boundary
                in state.boundaries.items()
            },
            "x": sorted(
                state.exhausted_kinds
            ),
        }

        signed_payload = signing.dumps(
            payload,
            salt=SQUARE_STABLE_CURSOR_SALT,
            compress=True,
        )

        return (
            f"{SQUARE_STABLE_CURSOR_PREFIX}"
            f"{signed_payload}"
        )

    @classmethod
    def decode(
        cls,
        raw_cursor: str,
        *,
        viewer,
        kind: str,
        mode: str | None,
    ) -> SquareStableCursorState:
        token = cls._cursor_token_only(
            raw_cursor
        )

        if not token or not token.startswith(
            SQUARE_STABLE_CURSOR_PREFIX
        ):
            raise SquareStableCursorError(
                "Unsupported Square cursor."
            )

        signed_payload = token[
            len(
                SQUARE_STABLE_CURSOR_PREFIX
            ):
        ]

        try:
            payload = signing.loads(
                signed_payload,
                salt=SQUARE_STABLE_CURSOR_SALT,
            )
        except signing.BadSignature as exc:
            raise SquareStableCursorError(
                "Invalid Square cursor."
            ) from exc

        if not isinstance(payload, dict):
            raise SquareStableCursorError(
                "Invalid Square cursor payload."
            )

        if payload.get("v") != (
            SQUARE_STABLE_CURSOR_VERSION
        ):
            raise SquareStableCursorError(
                "Unsupported Square cursor version."
            )

        expected_viewer_key = (
            cls.viewer_key(
                viewer
            )
        )

        expected_mode = str(
            mode or ""
        )

        if payload.get("u") != expected_viewer_key:
            raise SquareStableCursorError(
                "Square cursor viewer mismatch."
            )

        if payload.get("k") != kind:
            raise SquareStableCursorError(
                "Square cursor kind mismatch."
            )

        if payload.get("m") != expected_mode:
            raise SquareStableCursorError(
                "Square cursor mode mismatch."
            )

        source_kinds = cls._source_kinds(
            payload.get("s")
        )

        remaining_ids = cls._remaining_ids(
            payload.get("r"),
            source_kinds=source_kinds,
        )

        boundaries = cls._boundaries(
            payload.get("b"),
            source_kinds=source_kinds,
        )

        exhausted_kinds = {
            value
            for value in (
                payload.get("x") or []
            )
            if isinstance(value, str)
            and value in source_kinds
        }

        return SquareStableCursorState(
            viewer_key=expected_viewer_key,
            kind=kind,
            mode=expected_mode,
            source_kinds=source_kinds,
            remaining_ids=remaining_ids,
            boundaries=boundaries,
            exhausted_kinds=exhausted_kinds,
        )

    @staticmethod
    def viewer_key(
        viewer,
    ) -> str:
        if (
            viewer
            and getattr(
                viewer,
                "is_authenticated",
                False,
            )
        ):
            viewer_id = getattr(
                viewer,
                "id",
                None,
            )

            if viewer_id:
                return f"user:{int(viewer_id)}"

        return "anonymous"

    @staticmethod
    def _cursor_token_only(
        raw_cursor: str | None,
    ) -> str | None:
        if not raw_cursor:
            return None

        cursor = str(
            raw_cursor
        ).strip()

        if not cursor:
            return None

        if cursor.startswith(
            ("http://", "https://")
        ):
            try:
                query = parse_qs(
                    urlparse(cursor).query
                )

                return (
                    query.get(
                        "cursor",
                        [None],
                    )[0]
                    or None
                )
            except Exception:
                return None

        return cursor

    @staticmethod
    def _source_kinds(
        raw_value,
    ) -> list[str]:
        if not isinstance(
            raw_value,
            list,
        ):
            raise SquareStableCursorError(
                "Invalid Square cursor sources."
            )

        output: list[str] = []
        seen: set[str] = set()

        for value in raw_value:
            if not isinstance(
                value,
                str,
            ):
                continue

            cleaned = value.strip()

            if (
                not cleaned
                or cleaned in seen
            ):
                continue

            seen.add(
                cleaned
            )

            output.append(
                cleaned
            )

        if not output:
            raise SquareStableCursorError(
                "Square cursor has no sources."
            )

        return output

    @staticmethod
    def _remaining_ids(
        raw_value,
        *,
        source_kinds: list[str],
    ) -> dict[str, list[int]]:
        if not isinstance(
            raw_value,
            dict,
        ):
            return {
                kind: []
                for kind in source_kinds
            }

        output: dict[
            str,
            list[int],
        ] = {}

        for kind in source_kinds:
            values = raw_value.get(
                kind,
                [],
            )

            if not isinstance(
                values,
                list,
            ):
                values = []

            seen: set[int] = set()
            ids: list[int] = []

            for value in values:
                try:
                    object_id = int(
                        value
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if (
                    object_id <= 0
                    or object_id in seen
                ):
                    continue

                seen.add(
                    object_id
                )

                ids.append(
                    object_id
                )

            output[kind] = ids

        return output

    @staticmethod
    def _boundaries(
        raw_value,
        *,
        source_kinds: list[str],
    ) -> dict[
        str,
        SquareStableSourceBoundary,
    ]:
        if not isinstance(
            raw_value,
            dict,
        ):
            return {}

        output = {}

        for kind in source_kinds:
            raw_boundary = raw_value.get(
                kind
            )

            if (
                not isinstance(
                    raw_boundary,
                    list,
                )
                or len(raw_boundary) != 2
            ):
                continue

            published_at = parse_datetime(
                str(
                    raw_boundary[0]
                )
            )

            try:
                object_id = int(
                    raw_boundary[1]
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                published_at is None
                or object_id <= 0
            ):
                continue

            output[kind] = (
                SquareStableSourceBoundary(
                    published_at=published_at,
                    object_id=object_id,
                )
            )

        return output


class SquareStableFeedCursor:
    """
    Stateless Square pagination with a rolling ranked buffer.

    Stable chronological boundaries decide which candidates have been
    scanned. Ranking only decides which unshown scanned candidates appear
    next.

    Mutable scores therefore cannot make an emitted item re-enter the feed
    or make an unshown scanned item disappear.
    """

    def __init__(
        self,
        *,
        page_size: int,
    ):
        self.page_size = max(
            int(page_size),
            1,
        )

    def build_page(
        self,
        *,
        request,
        viewer,
        kind: str,
        mode: str | None,
        cursor: str | None,
    ) -> SquareStableFeedPage:
        ranked_querysets = (
            self._build_ranked_querysets(
                viewer=viewer,
                kind=kind,
                mode=mode,
            )
        )

        if not ranked_querysets:
            return SquareStableFeedPage(
                results=[],
                next_cursor=None,
            )

        if cursor:
            state = (
                SquareStableCursorCodec
                .decode(
                    cursor,
                    viewer=viewer,
                    kind=kind,
                    mode=mode,
                )
            )

            self._remove_missing_sources(
                state=state,
                ranked_querysets=
                    ranked_querysets,
            )

            buffer = (
                self._rehydrate_remaining(
                    state=state,
                    ranked_querysets=
                        ranked_querysets,
                )
            )
        else:
            source_kinds = sorted(
                ranked_querysets.keys()
            )

            state = SquareStableCursorState(
                viewer_key=(
                    SquareStableCursorCodec
                    .viewer_key(
                        viewer
                    )
                ),
                kind=kind,
                mode=str(
                    mode or ""
                ),
                source_kinds=
                    source_kinds,
                remaining_ids={
                    source_kind: []
                    for source_kind
                    in source_kinds
                },
            )

            buffer = []

            self._initial_scan(
                state=state,
                ranked_querysets=
                    ranked_querysets,
                buffer=buffer,
            )

        self._ensure_target_buffer(
            state=state,
            ranked_querysets=
                ranked_querysets,
            buffer=buffer,
        )

        results: list[dict] = []

        while len(results) < self.page_size:
            if not buffer:
                added = (
                    self._ensure_target_buffer(
                        state=state,
                        ranked_querysets=
                            ranked_querysets,
                        buffer=buffer,
                    )
                )

                if not added:
                    break

            ranked_buffer = (
                self._rank_objects(
                    buffer,
                    mode=mode,
                    viewer=viewer,
                )
            )

            page_results, remaining = (
                self._consume_serializable(
                    request=request,
                    objects=ranked_buffer,
                    result_limit=(
                        self.page_size
                        - len(results)
                    ),
                )
            )

            results.extend(
                page_results
            )

            buffer = remaining

            if (
                len(results)
                >= self.page_size
            ):
                break

            if buffer:
                continue

            if self._all_sources_exhausted(
                state
            ):
                break

        state.remaining_ids = (
            self._remaining_ids_from_objects(
                state=state,
                objects=buffer,
            )
        )

        has_more = (
            bool(buffer)
            or not self._all_sources_exhausted(
                state
            )
        )

        next_cursor = (
            SquareStableCursorCodec.encode(
                state
            )
            if has_more
            else None
        )

        return SquareStableFeedPage(
            results=results,
            next_cursor=next_cursor,
        )

    def _build_ranked_querysets(
        self,
        *,
        viewer,
        kind: str,
        mode: str | None,
    ) -> dict[str, QuerySet]:
        sources_by_model = {
            source.model: source
            for source in get_square_sources()
        }

        querysets = SquareQuery.build(
            viewer=viewer,
            kind=kind,
        )

        ranked: dict[
            str,
            QuerySet,
        ] = {}

        for queryset in querysets:
            source = sources_by_model.get(
                queryset.model
            )

            if source is None:
                continue

            ranked[
                source.kind
            ] = SquareEngine.apply(
                queryset=queryset,
                mode=mode,
                viewer=viewer,
            )

        return ranked

    def _initial_scan(
        self,
        *,
        state: SquareStableCursorState,
        ranked_querysets: dict[
            str,
            QuerySet,
        ],
        buffer: list,
    ) -> None:
        for kind in state.source_kinds:
            queryset = (
                ranked_querysets.get(
                    kind
                )
            )

            if queryset is None:
                state.exhausted_kinds.add(
                    kind
                )
                continue

            batch = self._scan_source(
                queryset=queryset,
                boundary=None,
                limit=(
                    SQUARE_STABLE_INITIAL_SCAN_PER_SOURCE
                ),
            )

            self._append_unique(
                buffer=buffer,
                objects=batch,
            )

            self._update_boundary(
                state=state,
                kind=kind,
                batch=batch,
            )

            if len(batch) < (
                SQUARE_STABLE_INITIAL_SCAN_PER_SOURCE
            ):
                state.exhausted_kinds.add(
                    kind
                )

    def _rehydrate_remaining(
        self,
        *,
        state: SquareStableCursorState,
        ranked_querysets: dict[
            str,
            QuerySet,
        ],
    ) -> list:
        buffer = []

        for kind in state.source_kinds:
            ids = state.remaining_ids.get(
                kind,
                [],
            )

            if not ids:
                continue

            queryset = (
                ranked_querysets.get(
                    kind
                )
            )

            if queryset is None:
                continue

            objects = list(
                queryset.filter(
                    pk__in=ids
                )
            )

            self._append_unique(
                buffer=buffer,
                objects=objects,
            )

        return buffer

    def _ensure_target_buffer(
        self,
        *,
        state: SquareStableCursorState,
        ranked_querysets: dict[
            str,
            QuerySet,
        ],
        buffer: list,
    ) -> bool:
        target_size = (
            SQUARE_STABLE_INITIAL_SCAN_PER_SOURCE
            * len(
                state.source_kinds
            )
        )

        added_any = False

        while len(buffer) < target_size:
            active_kinds = [
                kind
                for kind in state.source_kinds
                if (
                    kind
                    not in state.exhausted_kinds
                    and kind
                    in ranked_querysets
                )
            ]

            if not active_kinds:
                break

            deficit = (
                target_size
                - len(buffer)
            )

            per_source_limit = max(
                SQUARE_STABLE_REFILL_MIN_PER_SOURCE,
                ceil(
                    deficit
                    / len(active_kinds)
                ),
            )

            per_source_limit = min(
                per_source_limit,
                SQUARE_STABLE_INITIAL_SCAN_PER_SOURCE,
            )

            round_added = 0

            for kind in active_kinds:
                queryset = (
                    ranked_querysets[
                        kind
                    ]
                )

                boundary = (
                    state.boundaries.get(
                        kind
                    )
                )

                batch = self._scan_source(
                    queryset=queryset,
                    boundary=boundary,
                    limit=per_source_limit,
                )

                round_added += (
                    self._append_unique(
                        buffer=buffer,
                        objects=batch,
                    )
                )

                self._update_boundary(
                    state=state,
                    kind=kind,
                    batch=batch,
                )

                if len(batch) < (
                    per_source_limit
                ):
                    state.exhausted_kinds.add(
                        kind
                    )

            if round_added <= 0:
                break

            added_any = True

        return added_any

    @staticmethod
    def _scan_source(
        *,
        queryset: QuerySet,
        boundary:
            SquareStableSourceBoundary | None,
        limit: int,
    ) -> list:
        qs = queryset

        if boundary is not None:
            qs = qs.filter(
                Q(
                    published_at__lt=
                        boundary.published_at
                )
                | Q(
                    published_at=
                        boundary.published_at,
                    id__lt=
                        boundary.object_id,
                )
            )

        return list(
            qs.order_by(
                "-published_at",
                "-id",
            )[:limit]
        )

    @staticmethod
    def _update_boundary(
        *,
        state: SquareStableCursorState,
        kind: str,
        batch: list,
    ) -> None:
        if not batch:
            return

        last_object = batch[-1]

        published_at = getattr(
            last_object,
            "published_at",
            None,
        )

        object_id = getattr(
            last_object,
            "id",
            None,
        )

        if (
            published_at is None
            or object_id is None
        ):
            return

        state.boundaries[kind] = (
            SquareStableSourceBoundary(
                published_at=published_at,
                object_id=int(
                    object_id
                ),
            )
        )

    @staticmethod
    def _append_unique(
        *,
        buffer: list,
        objects: list,
    ) -> int:
        seen = {
            (
                str(
                    getattr(
                        obj,
                        "square_kind",
                        "",
                    )
                    or ""
                ),
                int(
                    getattr(
                        obj,
                        "id",
                        0,
                    )
                    or 0
                ),
            )
            for obj in buffer
        }

        added = 0

        for obj in objects:
            identity = (
                str(
                    getattr(
                        obj,
                        "square_kind",
                        "",
                    )
                    or ""
                ),
                int(
                    getattr(
                        obj,
                        "id",
                        0,
                    )
                    or 0
                ),
            )

            if (
                not identity[0]
                or identity[1] <= 0
                or identity in seen
            ):
                continue

            seen.add(
                identity
            )

            buffer.append(
                obj
            )

            added += 1

        return added

    @classmethod
    def _rank_objects(
        cls,
        objects: list,
        *,
        mode: str | None,
        viewer,
    ) -> list:
        return sorted(
            objects,
            key=lambda obj: (
                -cls._score_of(
                    obj,
                    mode=mode,
                    viewer=viewer,
                ),
                -cls._published_timestamp(
                    obj
                ),
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
            ),
        )

    @staticmethod
    def _score_of(
        obj,
        *,
        mode: str | None,
        viewer,
    ) -> float:
        if mode == (
            SquareEngine.MODE_TRENDING
        ):
            return float(
                getattr(
                    obj,
                    "trending_score",
                    0,
                )
                or 0
            )

        if (
            mode
            == SquareEngine.MODE_FOR_YOU
            and viewer
        ):
            return float(
                getattr(
                    obj,
                    "personalized_trending_score",
                    0,
                )
                or 0
            )

        if mode == (
            SquareEngine.MODE_RECENT
        ):
            return float(
                getattr(
                    obj,
                    "rank_score",
                    0,
                )
                or 0
            )

        return float(
            getattr(
                obj,
                "hybrid_score",
                0,
            )
            or 0
        )

    @staticmethod
    def _published_timestamp(
        obj,
    ) -> float:
        published_at = getattr(
            obj,
            "published_at",
            None,
        )

        if published_at is None:
            return 0.0

        try:
            return float(
                published_at.timestamp()
            )
        except Exception:
            return 0.0

    @staticmethod
    def _consume_serializable(
        *,
        request,
        objects: list,
        result_limit: int,
    ) -> tuple[
        list[dict],
        list,
    ]:
        if result_limit <= 0:
            return [], objects

        results: list[dict] = []
        remaining = list(
            objects
        )

        while (
            remaining
            and len(results)
            < result_limit
        ):
            chunk = remaining[
                :SQUARE_STABLE_SERIALIZATION_CHUNK
            ]

            representations = list(
                SquareItemSerializer(
                    chunk,
                    many=True,
                    context={
                        "request": request,
                    },
                ).data
            )

            consumed = 0

            for index, _obj in enumerate(
                chunk
            ):
                consumed = index + 1

                representation = (
                    representations[index]
                    if index
                    < len(representations)
                    else None
                )

                if representation is not None:
                    results.append(
                        representation
                    )

                if (
                    len(results)
                    >= result_limit
                ):
                    break

            remaining = (
                chunk[consumed:]
                + remaining[
                    len(chunk):
                ]
            )

        return results, remaining

    @staticmethod
    def _remaining_ids_from_objects(
        *,
        state: SquareStableCursorState,
        objects: list,
    ) -> dict[str, list[int]]:
        remaining = {
            kind: []
            for kind in state.source_kinds
        }

        seen = {
            kind: set()
            for kind in state.source_kinds
        }

        for obj in objects:
            kind = str(
                getattr(
                    obj,
                    "square_kind",
                    "",
                )
                or ""
            )

            if kind not in remaining:
                continue

            object_id = int(
                getattr(
                    obj,
                    "id",
                    0,
                )
                or 0
            )

            if (
                object_id <= 0
                or object_id
                in seen[kind]
            ):
                continue

            seen[kind].add(
                object_id
            )

            remaining[kind].append(
                object_id
            )

        return remaining

    @staticmethod
    def _remove_missing_sources(
        *,
        state: SquareStableCursorState,
        ranked_querysets: dict[
            str,
            QuerySet,
        ],
    ) -> None:
        for kind in state.source_kinds:
            if kind in ranked_querysets:
                continue

            state.exhausted_kinds.add(
                kind
            )

            state.remaining_ids[
                kind
            ] = []

    @staticmethod
    def _all_sources_exhausted(
        state: SquareStableCursorState,
    ) -> bool:
        return all(
            kind
            in state.exhausted_kinds
            for kind in state.source_kinds
        )