# apps/translations/services/base.py

from __future__ import annotations

import re

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.translations.models import TranslationCache
from apps.translations.selectors import get_cached_translation
from apps.translations.services.aws_translate import AWSTranslateClient
from apps.translations.services.exceptions import EmptySourceTextError
from apps.translations.services.hashing import hash_text
from apps.translations.services.language import resolve_target_language
from apps.translations.services.llm_humanize import humanize_translation


_PARAGRAPH_SEPARATOR = "\n\n"


def _humanize_enabled() -> bool:
    """
    Check whether LLM humanization is globally enabled.
    """
    return bool(
        getattr(
            settings,
            "TRANSLATIONS_HUMANIZE_ENABLED",
            False,
        )
    )


def _current_prompt_version() -> str:
    """
    Return the current humanization prompt version.
    """
    return getattr(
        settings,
        "TRANSLATIONS_HUMANIZE_PROMPT_VERSION",
        "",
    )


def _normalize_line_endings(
    value: str,
) -> str:
    """
    Normalize Windows and legacy line endings without removing
    intentional paragraphs.
    """
    return (
        value
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _split_paragraphs(
    value: str,
) -> list[str]:
    """
    Split text at one or more blank lines.

    Each returned paragraph is trimmed only at its outer edges.
    Internal punctuation and sentence structure remain unchanged.
    """
    normalized = _normalize_line_endings(
        value
    ).strip()

    if not normalized:
        return []

    paragraphs = re.split(
        r"\n[ \t]*\n+",
        normalized,
    )

    return [
        paragraph.strip()
        for paragraph in paragraphs
        if paragraph.strip()
    ]


def _join_paragraphs(
    paragraphs: list[str],
) -> str:
    """
    Rebuild translated content using canonical paragraph spacing.
    """
    return _PARAGRAPH_SEPARATOR.join(
        paragraph.strip()
        for paragraph in paragraphs
        if paragraph.strip()
    )


def _paragraph_count(
    value: str,
) -> int:
    return len(
        _split_paragraphs(value)
    )


def _cached_structure_is_valid(
    *,
    source_text: str,
    translated_text: str,
) -> bool:
    """
    A translated value must preserve the source paragraph count.

    Single-paragraph content is always considered structurally valid.
    """
    source_count = _paragraph_count(
        source_text
    )

    if source_count <= 1:
        return True

    translated_count = _paragraph_count(
        translated_text
    )

    return translated_count == source_count


def _translate_paragraphs_with_aws(
    *,
    source_text: str,
    target_language: str,
    source_language: str | None,
) -> dict:
    """
    Translate each paragraph separately so AWS cannot collapse
    paragraph boundaries.

    Returns:
        {
            "source_paragraphs": [...],
            "translated_paragraphs": [...],
            "source_language": "en",
        }
    """
    source_paragraphs = _split_paragraphs(
        source_text
    )

    if not source_paragraphs:
        raise EmptySourceTextError(
            "Source text is empty."
        )

    aws_client = AWSTranslateClient()

    translated_paragraphs: list[str] = []
    detected_source_language = (
        source_language
        or ""
    )

    for paragraph in source_paragraphs:
        result = aws_client.translate(
            text=paragraph,
            target_language=target_language,
            source_language=source_language,
        )

        translated_paragraph = (
            result.get("translated_text")
            or ""
        ).strip()

        if not translated_paragraph:
            translated_paragraph = paragraph

        translated_paragraphs.append(
            translated_paragraph
        )

        result_source_language = (
            result.get("source_language")
            or ""
        ).strip()

        if (
            not detected_source_language
            and result_source_language
        ):
            detected_source_language = (
                result_source_language
            )

    return {
        "source_paragraphs": source_paragraphs,
        "translated_paragraphs": translated_paragraphs,
        "source_language": (
            detected_source_language
            or source_language
            or "auto"
        ),
    }


def _humanize_paragraphs(
    *,
    source_paragraphs: list[str],
    translated_paragraphs: list[str],
    target_language: str,
) -> dict:
    """
    Humanize each paragraph independently.

    This guarantees that the LLM cannot merge several source
    paragraphs into one translated block.
    """
    if (
        len(source_paragraphs)
        != len(translated_paragraphs)
    ):
        raise RuntimeError(
            "Source and translated paragraph counts do not match."
        )

    final_paragraphs: list[str] = []

    llm_model = ""
    prompt_version = ""

    for source_paragraph, translated_paragraph in zip(
        source_paragraphs,
        translated_paragraphs,
        strict=True,
    ):
        result = humanize_translation(
            source_text=source_paragraph,
            translated_text=translated_paragraph,
            target_language=target_language,
        )

        final_paragraph = (
            result.get("text")
            or translated_paragraph
        ).strip()

        final_paragraphs.append(
            final_paragraph
        )

        if not llm_model:
            llm_model = (
                result.get("model")
                or ""
            )

        if not prompt_version:
            prompt_version = (
                result.get("prompt_version")
                or ""
            )

    return {
        "text": _join_paragraphs(
            final_paragraphs
        ),
        "model": llm_model,
        "prompt_version": prompt_version,
    }


def _rehumanize_cached_translation(
    *,
    source_text: str,
    translated_text: str,
    target_language: str,
) -> dict:
    """
    Humanize an existing structurally valid cache entry while
    preserving all paragraph boundaries.
    """
    source_paragraphs = _split_paragraphs(
        source_text
    )

    translated_paragraphs = _split_paragraphs(
        translated_text
    )

    return _humanize_paragraphs(
        source_paragraphs=source_paragraphs,
        translated_paragraphs=translated_paragraphs,
        target_language=target_language,
    )


def translate_cached(
    *,
    obj,
    field_name: str,
    user=None,
    target_language: str | None = None,
    source_language: str | None = None,
) -> dict:
    """
    Translate a model text field with cache support.

    Guarantees:
    - Source paragraph boundaries are preserved.
    - AWS translates each paragraph independently.
    - LLM humanization runs independently for each paragraph.
    - Structurally invalid old cache entries are regenerated.
    - Final translated content is stored with canonical blank lines.
    """

    # -------------------------------------------------
    # 0) Source validation
    # -------------------------------------------------

    raw_source_text = getattr(
        obj,
        field_name,
        None,
    )

    if not raw_source_text:
        raise EmptySourceTextError(
            "Source text is empty."
        )

    source_text = _normalize_line_endings(
        str(raw_source_text)
    ).strip()

    if not source_text:
        raise EmptySourceTextError(
            "Source text is empty."
        )

    source_text_hash = hash_text(
        source_text
    )

    content_type = ContentType.objects.get_for_model(
        obj
    )

    resolved_target_language = resolve_target_language(
        user=user,
        source_language=source_language,
        override_language=target_language,
    )

    current_prompt_version = (
        _current_prompt_version()
    )

    # -------------------------------------------------
    # 1) Try cache
    # -------------------------------------------------

    cached = get_cached_translation(
        content_type=content_type,
        object_id=obj.pk,
        field_name=field_name,
        target_language=resolved_target_language,
        source_text_hash=source_text_hash,
    )

    if cached:
        structure_is_valid = (
            _cached_structure_is_valid(
                source_text=source_text,
                translated_text=cached.translated_text,
            )
        )

        if not structure_is_valid:
            # The previous implementation collapsed paragraphs.
            # Remove only this invalid cache row and regenerate it.
            cached.delete()
            cached = None

    if cached:
        cached.touch()

        needs_upgrade = (
            _humanize_enabled()
            and (
                not cached.is_humanized
                or (
                    cached.prompt_version
                    != current_prompt_version
                )
            )
        )

        if needs_upgrade:
            try:
                humanized = (
                    _rehumanize_cached_translation(
                        source_text=source_text,
                        translated_text=cached.translated_text,
                        target_language=resolved_target_language,
                    )
                )

                cached.translated_text = (
                    humanized["text"]
                )
                cached.engine = "aws+llm"
                cached.is_humanized = True
                cached.llm_model = (
                    humanized["model"]
                )
                cached.prompt_version = (
                    humanized["prompt_version"]
                )
                cached.humanized_at = timezone.now()

                cached.save(
                    update_fields=[
                        "translated_text",
                        "engine",
                        "is_humanized",
                        "llm_model",
                        "prompt_version",
                        "humanized_at",
                    ]
                )

            except Exception:
                # Fail-safe: retain the existing structurally
                # valid cached translation.
                pass

        return {
            "text": cached.translated_text,
            "source_language": (
                cached.source_language
            ),
            "target_language": (
                cached.target_language
            ),
            "cached": True,
        }

    # -------------------------------------------------
    # 2) AWS base translation, paragraph by paragraph
    # -------------------------------------------------

    aws_result = _translate_paragraphs_with_aws(
        source_text=source_text,
        target_language=resolved_target_language,
        source_language=source_language,
    )

    source_paragraphs = aws_result[
        "source_paragraphs"
    ]

    translated_paragraphs = aws_result[
        "translated_paragraphs"
    ]

    final_text = _join_paragraphs(
        translated_paragraphs
    )

    engine = "aws"
    is_humanized = False
    llm_model = ""
    prompt_version = ""
    humanized_at = None

    # -------------------------------------------------
    # 3) LLM humanization, paragraph by paragraph
    # -------------------------------------------------

    if _humanize_enabled():
        try:
            humanized = _humanize_paragraphs(
                source_paragraphs=source_paragraphs,
                translated_paragraphs=translated_paragraphs,
                target_language=resolved_target_language,
            )

            final_text = humanized["text"]
            engine = "aws+llm"
            is_humanized = True
            llm_model = humanized["model"]
            prompt_version = humanized[
                "prompt_version"
            ]
            humanized_at = timezone.now()

        except Exception:
            # Fail-safe: keep the paragraph-preserving
            # AWS translation.
            pass

    # -------------------------------------------------
    # 4) Store cache
    # -------------------------------------------------

    TranslationCache.objects.create(
        content_type=content_type,
        object_id=obj.pk,
        field_name=field_name,
        source_language=aws_result[
            "source_language"
        ],
        target_language=resolved_target_language,
        source_text_hash=source_text_hash,
        translated_text=final_text,
        last_accessed_at=timezone.now(),
        engine=engine,
        is_humanized=is_humanized,
        llm_model=llm_model,
        prompt_version=prompt_version,
        humanized_at=humanized_at,
    )

    return {
        "text": final_text,
        "source_language": aws_result[
            "source_language"
        ],
        "target_language": (
            resolved_target_language
        ),
        "cached": False,
    }