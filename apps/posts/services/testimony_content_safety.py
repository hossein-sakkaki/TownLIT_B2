# apps/posts/services/testimony_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from django.conf import settings

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety
from apps.posts.models.testimony import Testimony


_DEFAULT_TESTIMONY_CHUNK_CHARS = 12_000


def enforce_testimony_content_safety(
    *,
    validated_data: dict,
    actor,
    instance: Testimony | None = None,
) -> None:
    """
    Enforce Content Safety for Testimony text.

    Covered fields:
    - title: written/audio/video testimony
    - content: written testimony only

    Written testimony may be substantially longer than other UGC surfaces,
    so it is inspected in context-preserving chunks.
    """

    testimony_type = validated_data.get(
        "type",
        instance.type
        if instance is not None
        else None,
    )

    _enforce_title_safety(
        validated_data=validated_data,
        actor=actor,
        instance=instance,
    )

    if testimony_type != Testimony.TYPE_WRITTEN:
        return

    _enforce_written_content_safety(
        validated_data=validated_data,
        actor=actor,
        instance=instance,
    )


def _enforce_title_safety(
    *,
    validated_data: dict,
    actor,
    instance: Testimony | None,
) -> None:
    """
    Inspect title only when supplied and changed.
    """

    if "title" not in validated_data:
        return

    title = validated_data.get(
        "title"
    )

    if (
        instance is not None
        and title == instance.title
    ):
        return

    enforce_text_safety(
        text=title,
        context=SafetyContext.TESTIMONY,
        actor=actor,
        field_name="title",
    )


def _enforce_written_content_safety(
    *,
    validated_data: dict,
    actor,
    instance: Testimony | None,
) -> None:
    """
    Inspect written testimony only when supplied and changed.
    """

    if "content" not in validated_data:
        return

    content = validated_data.get(
        "content"
    )

    if (
        instance is not None
        and content == instance.content
    ):
        return

    if content is None:
        return

    text = str(
        content
    )

    if not text.strip():
        return

    chunks = _testimony_text_chunks(
        text
    )

    for chunk in chunks:
        enforce_text_safety(
            text=chunk,
            context=SafetyContext.TESTIMONY,
            actor=actor,
            field_name="content",
        )


def _testimony_text_chunks(
    text: str,
) -> list[str]:
    """
    Split long testimony text while preserving paragraphs whenever possible.

    This does not truncate or drop any meaningful testimony text.
    """

    limit = _resolved_chunk_limit()

    if len(text) <= limit:
        return [
            text
        ]

    paragraphs = text.split(
        "\n\n"
    )

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not paragraph:
            if current:
                candidate = (
                    f"{current}\n\n"
                )

                if len(candidate) <= limit:
                    current = candidate

            continue

        if len(paragraph) > limit:
            if current.strip():
                chunks.append(
                    current
                )
                current = ""

            chunks.extend(
                _split_oversized_segment(
                    paragraph,
                    limit=limit,
                )
            )

            continue

        candidate = (
            paragraph
            if not current
            else f"{current}\n\n{paragraph}"
        )

        if len(candidate) <= limit:
            current = candidate
            continue

        if current.strip():
            chunks.append(
                current
            )

        current = paragraph

    if current.strip():
        chunks.append(
            current
        )

    return chunks


def _split_oversized_segment(
    text: str,
    *,
    limit: int,
) -> list[str]:
    """
    Split one exceptionally large paragraph without losing content.
    """

    words = text.split()

    if not words:
        return [
            text[index:index + limit]
            for index in range(
                0,
                len(text),
                limit,
            )
        ]

    chunks: list[str] = []
    current = ""

    for word in words:
        if len(word) > limit:
            if current:
                chunks.append(
                    current
                )
                current = ""

            chunks.extend(
                word[index:index + limit]
                for index in range(
                    0,
                    len(word),
                    limit,
                )
            )

            continue

        candidate = (
            word
            if not current
            else f"{current} {word}"
        )

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(
                current
            )

        current = word

    if current:
        chunks.append(
            current
        )

    return chunks


def _resolved_chunk_limit() -> int:
    """
    Keep every testimony chunk below the global safety inspection ceiling.
    """

    configured_limit = int(
        getattr(
            settings,
            "CONTENT_SAFETY_MAX_TEXT_CHARS",
            20_000,
        )
        or 20_000
    )

    return max(
        1,
        min(
            configured_limit,
            _DEFAULT_TESTIMONY_CHUNK_CHARS,
        ),
    )