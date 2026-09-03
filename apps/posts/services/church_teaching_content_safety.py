# apps/posts/services/church_teaching_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.conf import settings

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.image import enforce_image_file_safety
from apps.content_safety.services.text import enforce_text_safety


_DEFAULT_TEACHING_CHUNK_CHARS = 12_000


def _chunk_limit() -> int:
    configured = int(
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
            configured,
            _DEFAULT_TEACHING_CHUNK_CHARS,
        ),
    )


def _split_long_segment(text: str, *, limit: int) -> list[str]:
    words = text.split()

    if not words:
        return [
            text[index:index + limit]
            for index in range(0, len(text), limit)
        ]

    chunks = []
    current = ""

    for word in words:
        if len(word) > limit:
            if current:
                chunks.append(current)
                current = ""

            chunks.extend(
                word[index:index + limit]
                for index in range(0, len(word), limit)
            )
            continue

        candidate = word if not current else f"{current} {word}"

        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)

        current = word

    if current:
        chunks.append(current)

    return chunks


def _teaching_text_chunks(text: str) -> list[str]:
    """Split long teaching text without dropping source content."""

    limit = _chunk_limit()

    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""

    for paragraph in text.split("\n\n"):
        if len(paragraph) > limit:
            if current.strip():
                chunks.append(current)
                current = ""

            chunks.extend(
                _split_long_segment(
                    paragraph,
                    limit=limit,
                )
            )
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"

        if len(candidate) <= limit:
            current = candidate
            continue

        if current.strip():
            chunks.append(current)

        current = paragraph

    if current.strip():
        chunks.append(current)

    return chunks


def _enforce_field_text(*, value, actor, field_name: str) -> None:
    if value is None:
        return

    text = str(value).strip()

    if not text:
        return

    chunks = _teaching_text_chunks(text)

    for index, chunk in enumerate(chunks):
        audit_field_name = (
            field_name
            if len(chunks) == 1
            else f"{field_name}[{index}]"
        )

        enforce_text_safety(
            text=chunk,
            context=SafetyContext.GENERIC,
            actor=actor,
            field_name=audit_field_name,
        )


def enforce_church_teaching_text_safety(
    *,
    title=None,
    excerpt=None,
    body=None,
    speaker_name=None,
    actor,
) -> None:
    """Check newly supplied Church teaching text before persistence."""

    for field_name, value in (
        ("title", title),
        ("excerpt", excerpt),
        ("body", body),
        ("speaker_name", speaker_name),
    ):
        _enforce_field_text(
            value=value,
            actor=actor,
            field_name=field_name,
        )



def enforce_church_teaching_series_text_safety(
    *,
    name=None,
    description=None,
    actor,
) -> None:
    """Check public teaching-series text before persistence."""

    _enforce_field_text(
        value=name,
        actor=actor,
        field_name="series_name",
    )
    _enforce_field_text(
        value=description,
        actor=actor,
        field_name="series_description",
    )

def enforce_church_teaching_thumbnail_safety(
    *,
    thumbnail,
    actor,
) -> None:
    """Check an uploaded Church teaching thumbnail before persistence."""

    if not thumbnail:
        return

    enforce_image_file_safety(
        file_obj=thumbnail,
        context=SafetyContext.GENERIC,
        actor=actor,
        field_name="thumbnail",
        mime_type=getattr(thumbnail, "content_type", None),
    )
