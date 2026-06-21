# apps/core/streams/context.py

from dataclasses import dataclass
from urllib.parse import unquote_plus

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
        """
        A true first page has no cursor and extension=0.

        This is important because profile streams use cursor pagination while
        keeping extension=0.
        """

        return self.extension == 0 and self.cursor is None


def parse_stream_context(request) -> StreamContext:
    """
    Parse and normalize stream query params.
    """

    viewer = request.user if request.user.is_authenticated else None

    kind = clean_query_value(
        request.query_params.get("kind")
    ) or ""

    seed_id_raw = clean_query_value(
        request.query_params.get("seed_id")
    ) or ""

    scope = clean_query_value(
        request.query_params.get("scope")
    ) or STREAM_SCOPE_SQUARE

    mode = clean_query_value(
        request.query_params.get("mode")
    ) or STREAM_MODE_RELATED

    username = clean_query_value(
        request.query_params.get("username")
    )

    seed_id = parse_int(
        seed_id_raw,
        fallback=0,
    )

    extension_raw = (
        request.query_params.get("ext")
        or request.query_params.get("extension")
        or 0
    )

    extension = max(
        parse_int(
            extension_raw,
            fallback=0,
        ),
        0,
    )

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

    Defensive note:
    Cursor timestamps contain timezone offsets like +00:00. In query strings,
    '+' may arrive as a space depending on client/proxy decoding. We normalize
    that back before calling parse_datetime.
    """

    cleaned = clean_query_value(raw)

    if not cleaned:
        return None

    try:
        cleaned = unquote_plus(cleaned)
        cleaned = cleaned.replace(" ", "+")

        if "|" not in cleaned:
            return None

        published_at_raw, id_raw = cleaned.rsplit("|", 1)

        published_at_raw = clean_query_value(published_at_raw)
        id_raw = clean_query_value(id_raw)

        if not published_at_raw or not id_raw:
            return None

        published_at = parse_datetime(published_at_raw)
        object_id = parse_int(
            id_raw,
            fallback=0,
        )

        if not published_at or object_id <= 0:
            return None

        return StreamCursor(
            published_at=published_at,
            object_id=object_id,
        )

    except Exception:
        return None


def parse_int(
    value,
    *,
    fallback: int,
) -> int:
    try:
        cleaned = clean_query_value(value)

        if not cleaned:
            return fallback

        return int(cleaned)
    except Exception:
        return fallback


def clean_query_value(value) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()

    return cleaned or None