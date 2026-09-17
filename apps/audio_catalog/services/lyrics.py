# apps/audio_catalog/services/lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from collections.abc import Iterable

from apps.audio_catalog.models.lyrics import (
    MusicLyrics,
)


def published_lyrics_for_track(
    track,
) -> list[MusicLyrics]:
    """
    Return public lyrics documents with line and word timing prefetched.

    Word timing remains optional so existing line-synchronized lyrics stay
    backward compatible.
    """

    documents = list(
        MusicLyrics.objects
        .filter(
            track=track,
            status=(
                MusicLyrics
                .Status
                .PUBLISHED
            ),
        )
        .select_related(
            "track",
            "reference_variant",
            "rights_record",
        )
        .prefetch_related(
            "lines__words"
        )
        .order_by(
            "-is_default",
            "language_code",
            "kind",
            "id",
        )
    )

    return [
        document
        for document in documents
        if _is_publicly_renderable(
            document
        )
    ]


def select_published_lyrics(
    documents: Iterable[
        MusicLyrics
    ],
    *,
    track_language_code: str = "",
    language_code: str = "",
    kind: str = "",
) -> MusicLyrics | None:
    """
    Resolve one deterministic lyrics document for playback presentation.
    """

    items = list(
        documents
    )

    if not items:
        return None

    requested_language = (
        MusicLyrics
        .normalize_language_code(
            language_code
        )
    )

    track_language = (
        MusicLyrics
        .normalize_language_code(
            track_language_code
        )
    )

    requested_kind = str(
        kind
        or ""
    ).strip().lower()

    if (
        requested_language
        and requested_kind
    ):
        match = _first(
            items,
            language_code=(
                requested_language
            ),
            kind=requested_kind,
        )

        if match is not None:
            return match

    if requested_language:
        matches = [
            item
            for item in items
            if (
                item.language_code
                == requested_language
            )
        ]

        match = _preferred_kind(
            matches
        )

        if match is not None:
            return match

    if requested_kind:
        match = next(
            (
                item
                for item in items
                if (
                    item.kind
                    == requested_kind
                )
            ),
            None,
        )

        if match is not None:
            return match

    default = next(
        (
            item
            for item in items
            if item.is_default
        ),
        None,
    )

    if default is not None:
        return default

    if track_language:
        match = _preferred_kind(
            [
                item
                for item in items
                if (
                    item.language_code
                    == track_language
                )
            ]
        )

        if match is not None:
            return match

    original = next(
        (
            item
            for item in items
            if (
                item.kind
                == MusicLyrics
                .Kind
                .ORIGINAL
            )
        ),
        None,
    )

    return (
        original
        or items[
            0
        ]
    )


def _first(
    items: list[
        MusicLyrics
    ],
    *,
    language_code: str,
    kind: str,
) -> MusicLyrics | None:
    return next(
        (
            item
            for item in items
            if (
                item.language_code
                == language_code
                and item.kind
                == kind
            )
        ),
        None,
    )


def _preferred_kind(
    items: list[
        MusicLyrics
    ],
) -> MusicLyrics | None:
    if not items:
        return None

    default = next(
        (
            item
            for item in items
            if item.is_default
        ),
        None,
    )

    if default is not None:
        return default

    original = next(
        (
            item
            for item in items
            if (
                item.kind
                == MusicLyrics
                .Kind
                .ORIGINAL
            )
        ),
        None,
    )

    return (
        original
        or items[
            0
        ]
    )


def _is_publicly_renderable(
    document: MusicLyrics,
) -> bool:
    lines = list(
        document.lines.all()
    )

    if (
        document.timing_mode
        == MusicLyrics.TimingMode.LINE
    ):
        return (
            bool(
                lines
            )
            and all(
                bool(
                    (
                        line.text
                        or ""
                    ).strip()
                )
                and (
                    line.start_ms
                    is not None
                )
                for line in lines
            )
        )

    if (
        document.plain_text
        or ""
    ).strip():
        return True

    return any(
        bool(
            (
                line.text
                or ""
            ).strip()
        )
        for line in lines
    )