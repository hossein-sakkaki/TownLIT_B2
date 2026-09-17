# apps/audio_catalog/tasks.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

import importlib

from celery import shared_task
from django.db import OperationalError

from apps.audio_catalog.models import MusicLyrics
from apps.audio_catalog.services.lyrics_processing import (
    mark_alignment_processing_state,
    process_music_lyrics_alignment,
    validate_music_lyrics_alignment_candidate,
)


@shared_task(
    bind=True,
    queue="lyrics_alignment",
    ignore_result=True,
    max_retries=2,
)
def align_music_lyrics_task(
    self,
    *,
    lyrics_id: int,
) -> None:
    """
    Generate and atomically persist automatic word-level music lyrics timing.

    Deterministic alignment and quality failures are never retried.
    Only known transient provider, network, or database failures may retry.
    """

    try:
        mark_alignment_processing_state(
            lyrics_id=lyrics_id,
            processing_state="running",
        )

        process_music_lyrics_alignment(
            lyrics_id=lyrics_id,
        )

    except Exception as exc:
        error_text = _safe_error_text(exc)

        if (
            _is_transient_exception(exc)
            and self.request.retries < self.max_retries
        ):
            _safe_mark_processing_state(
                lyrics_id=lyrics_id,
                processing_state="retrying",
                error=error_text,
            )

            countdown = 30 * (2 ** self.request.retries)

            raise self.retry(
                exc=exc,
                countdown=countdown,
            )

        _safe_mark_processing_state(
            lyrics_id=lyrics_id,
            processing_state="failed",
            error=error_text,
        )

        raise


def enqueue_music_lyrics_alignment(
    lyrics: MusicLyrics,
) -> str:
    """
    Validate and enqueue one lyrics document on the dedicated ML worker.
    """

    validate_music_lyrics_alignment_candidate(lyrics)

    async_result = align_music_lyrics_task.apply_async(
        kwargs={
            "lyrics_id": lyrics.pk,
        },
        queue="lyrics_alignment",
    )

    return str(async_result.id)


def _safe_mark_processing_state(
    *,
    lyrics_id: int,
    processing_state: str,
    error: str,
) -> None:
    try:
        mark_alignment_processing_state(
            lyrics_id=lyrics_id,
            processing_state=processing_state,
            error=error,
        )
    except Exception:
        # Never hide the original processing failure with metadata bookkeeping.
        pass


def _safe_error_text(
    exc: Exception,
) -> str:
    message = str(exc or "").strip()

    if message:
        return f"{type(exc).__name__}: {message}"[:500]

    return type(exc).__name__


def _is_transient_exception(
    exc: Exception,
) -> bool:
    if isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            OperationalError,
        ),
    ):
        return True

    if _matches_optional_exception(
        exc,
        module_name="openai",
        class_names=(
            "APIConnectionError",
            "APITimeoutError",
            "RateLimitError",
            "InternalServerError",
        ),
    ):
        return True

    if _matches_optional_exception(
        exc,
        module_name="botocore.exceptions",
        class_names=(
            "EndpointConnectionError",
            "ConnectionClosedError",
            "ReadTimeoutError",
            "ConnectTimeoutError",
        ),
    ):
        return True

    return False


def _matches_optional_exception(
    exc: Exception,
    *,
    module_name: str,
    class_names: tuple[str, ...],
) -> bool:
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return False

    exception_types = tuple(
        exception_type
        for name in class_names
        if isinstance(
            exception_type := getattr(module, name, None),
            type,
        )
    )

    return bool(
        exception_types
        and isinstance(exc, exception_types)
    )