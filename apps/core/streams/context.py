# apps/core/streams/context.py

from dataclasses import dataclass

from django.utils.dateparse import parse_datetime

from apps.core.streams.constants import (
    STREAM_SCOPE_SQUARE,
    STREAM_MODE_RELATED,
)


@dataclass(frozen=True)
class StreamCursor:
    """
    Parsed cursor value.
    """

    published_at: object
    object_id: int


@dataclass(frozen=True)
class StreamContext:
    """
    Request context for universal stream.
    """

    kind: str
    seed_id: int
    scope: str
    mode: str
    cursor: StreamCursor | None
    extension: int
    username: str | None
    viewer: object | None

    @property
    def is_first_page(self) -> bool:
        
        return self.cursor is None


def parse_stream_context(request) -> StreamContext:
    """
    Parse and normalize stream query params.
    """

    viewer = request.user if request.user.is_authenticated else None

    kind = (request.query_params.get("kind") or "").strip()
    seed_id_raw = (request.query_params.get("seed_id") or "").strip()
    scope = (request.query_params.get("scope") or STREAM_SCOPE_SQUARE).strip()
    mode = (request.query_params.get("mode") or STREAM_MODE_RELATED).strip()
    username = (request.query_params.get("username") or "").strip() or None

    try:
        seed_id = int(seed_id_raw)
    except Exception:
        seed_id = 0

    extension_raw = (
        request.query_params.get("ext")
        or request.query_params.get("extension")
        or 0
    )

    try:
        extension = max(int(extension_raw), 0)
    except Exception:
        extension = 0

    cursor = parse_stream_cursor(
        request.query_params.get("cursor")
    )

    return StreamContext(
        kind=kind,
        seed_id=seed_id,
        scope=scope,
        mode=mode,
        cursor=cursor,
        extension=extension,
        username=username,
        viewer=viewer,
    )


def parse_stream_cursor(raw: str | None) -> StreamCursor | None:
    """
    Parse cursor format: published_at|id
    """

    if not raw:
        return None

    try:
        published_at_raw, id_raw = raw.split("|")
        published_at = parse_datetime(published_at_raw)
        object_id = int(id_raw)

        if not published_at:
            return None

        return StreamCursor(
            published_at=published_at,
            object_id=object_id,
        )

    except Exception:
        return None