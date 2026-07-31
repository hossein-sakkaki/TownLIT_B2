# apps/translations/services/base.py

from __future__ import annotations

import re

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.translations.models import TranslationCache
from apps.translations.selectors import (
    get_cached_translation,
)
from apps.translations.services.aws_translate import (
    AWSTranslateClient,
)
from apps.translations.services.exceptions import (
    EmptySourceTextError,
)
from apps.translations.services.hashing import (
    hash_text,
)
from apps.translations.services.language import (
    DEFAULT_SOURCE_LANGUAGE,
    language_codes_match,
    resolve_target_language,
)
from apps.translations.services.llm_humanize import (
    humanize_translation,
)
import logging

logger = logging.getLogger(
    __name__
)

_PARAGRAPH_SEPARATOR = "\n\n"


def humanize_enabled() -> bool:
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

    return str(
        getattr(
            settings,
            "TRANSLATIONS_HUMANIZE_PROMPT_VERSION",
            "",
        )
        or ""
    )


def _normalize_line_endings(
    value: str,
) -> str:
    """
    Normalize line endings without removing paragraphs.
    """

    return (
        value
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _normalize_source_text(
    value,
) -> str:
    """
    Normalize and validate source text.
    """

    if value is None:
        raise EmptySourceTextError(
            "Source text is empty."
        )

    source_text = _normalize_line_endings(
        str(value)
    ).strip()

    if not source_text:
        raise EmptySourceTextError(
            "Source text is empty."
        )

    return source_text


def _normalize_cache_field_name(
    value: str,
) -> str:
    """
    Normalize one logical translation field name.
    """

    field_name = str(
        value or ""
    ).strip()

    if not field_name:
        raise ValueError(
            "Translation field name is required."
        )

    if len(field_name) > 50:
        raise ValueError(
            "Translation field name cannot exceed 50 characters."
        )

    return field_name


def _split_paragraphs(
    value: str,
) -> list[str]:
    """
    Split text at one or more blank lines.
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
    Rebuild content using canonical paragraph spacing.
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
        _split_paragraphs(
            value
        )
    )


def _cached_structure_is_valid(
    *,
    source_text: str,
    translated_text: str,
) -> bool:
    """
    Ensure translated content preserves paragraph count.
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
    Translate each paragraph independently.
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

    detected_source_language = str(
        source_language or ""
    ).strip()

    for paragraph in source_paragraphs:
        result = aws_client.translate(
            text=paragraph,
            target_language=target_language,
            source_language=source_language,
        )

        translated_paragraph = str(
            result.get("translated_text")
            or ""
        ).strip()

        if not translated_paragraph:
            translated_paragraph = paragraph

        translated_paragraphs.append(
            translated_paragraph
        )

        result_source_language = str(
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
    Humanize each translated paragraph independently.
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

        final_paragraph = str(
            result.get("text")
            or translated_paragraph
        ).strip()

        final_paragraphs.append(
            final_paragraph
        )

        if not llm_model:
            llm_model = str(
                result.get("model")
                or ""
            )

        if not prompt_version:
            prompt_version = str(
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
    Upgrade an existing cache entry safely.
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


def _translation_result_from_cache(
    cached: TranslationCache,
) -> dict:
    """
    Build the public translation result.
    """

    return {
        "text": cached.translated_text,
        "source_language": cached.source_language,
        "target_language": cached.target_language,
        "cached": True,
        "engine": cached.engine,
        "is_humanized": cached.is_humanized,
        "llm_model": cached.llm_model,
        "prompt_version": cached.prompt_version,
        "cache_id": cached.pk,
    }


def _upgrade_cached_translation_if_needed(
    *,
    cached: TranslationCache,
    source_text: str,
    target_language: str,
) -> None:
    """
    Upgrade one cache row to the current humanization version.
    """

    if not humanize_enabled():
        return

    current_prompt_version = (
        _current_prompt_version()
    )

    needs_upgrade = (
        not cached.is_humanized
        or cached.prompt_version
        != current_prompt_version
    )

    if not needs_upgrade:
        return

    try:
        humanized = (
            _rehumanize_cached_translation(
                source_text=source_text,
                translated_text=cached.translated_text,
                target_language=target_language,
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
        cached.humanized_at = (
            timezone.now()
        )

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
        logger.exception(
            "[translation] cached humanization upgrade failed "
            "cache_id=%s field=%s target_language=%s",
            cached.pk,
            cached.field_name,
            target_language,
        )
        return


def _find_valid_cached_translation(
    *,
    content_type: ContentType,
    object_id: int,
    field_name: str,
    target_language: str,
    source_text_hash: str,
    source_text: str,
    allow_humanize: bool,
) -> TranslationCache | None:
    """
    Return a structurally valid cache row.
    """

    cached = get_cached_translation(
        content_type=content_type,
        object_id=object_id,
        field_name=field_name,
        target_language=target_language,
        source_text_hash=source_text_hash,
    )

    if cached is None:
        return None

    if not _cached_structure_is_valid(
        source_text=source_text,
        translated_text=cached.translated_text,
    ):
        cached.delete()
        return None

    cached.touch()

    if allow_humanize:
        _upgrade_cached_translation_if_needed(
            cached=cached,
            source_text=source_text,
            target_language=target_language,
        )

    return cached


def _same_language_result(
    *,
    source_text: str,
    source_language: str,
    target_language: str,
) -> dict:
    """
    Return original text when translation is unnecessary.
    """

    return {
        "text": source_text,
        "source_language": source_language,
        "target_language": target_language,
        "cached": True,
        "engine": "original",
        "is_humanized": False,
        "llm_model": "",
        "prompt_version": "",
        "cache_id": None,
    }


def _create_translation_cache_safely(
    *,
    content_type: ContentType,
    object_id: int,
    field_name: str,
    source_language: str,
    target_language: str,
    source_text_hash: str,
    translated_text: str,
    engine: str,
    is_humanized: bool,
    llm_model: str,
    prompt_version: str,
    humanized_at,
) -> tuple[TranslationCache, bool]:
    """
    Create one cache row with race protection.

    Returns:
        cache_row, created
    """

    try:
        with transaction.atomic():
            cached = TranslationCache.objects.create(
                content_type=content_type,
                object_id=object_id,
                field_name=field_name,
                source_language=source_language,
                target_language=target_language,
                source_text_hash=source_text_hash,
                translated_text=translated_text,
                last_accessed_at=timezone.now(),
                engine=engine,
                is_humanized=is_humanized,
                llm_model=llm_model,
                prompt_version=prompt_version,
                humanized_at=humanized_at,
            )

        return cached, True

    except IntegrityError:
        cached = TranslationCache.objects.get(
            content_type=content_type,
            object_id=object_id,
            field_name=field_name,
            target_language=target_language,
            source_text_hash=source_text_hash,
        )

        cached.touch()

        return cached, False


def translate_text_cached(
    *,
    obj,
    field_name: str,
    source_text,
    user=None,
    target_language: str | None = None,
    source_language: str | None = None,
    humanize: bool | None = None,
) -> dict:
    """
    Translate arbitrary text with model-backed cache support.

    humanize:
    - None: follow the global setting.
    - True: humanize when globally enabled.
    - False: return the base/cache translation without individual humanization.
    """

    if obj is None:
        raise ValueError(
            "Translation cache object is required."
        )

    if not getattr(
        obj,
        "pk",
        None,
    ):
        raise ValueError(
            "Translation cache object must be saved."
        )

    normalized_field_name = _normalize_cache_field_name(
        field_name
    )

    normalized_source_text = _normalize_source_text(
        source_text
    )

    resolved_source_language = str(
        source_language
        or DEFAULT_SOURCE_LANGUAGE
    ).strip()

    resolved_target_language = resolve_target_language(
        user=user,
        source_language=resolved_source_language,
        override_language=target_language,
    )

    should_humanize = (
        humanize_enabled()
        if humanize is None
        else humanize_enabled()
        and bool(humanize)
    )

    if language_codes_match(
        resolved_source_language,
        resolved_target_language,
    ):
        return _same_language_result(
            source_text=normalized_source_text,
            source_language=resolved_source_language,
            target_language=resolved_target_language,
        )

    source_text_hash = hash_text(
        normalized_source_text
    )

    content_type = ContentType.objects.get_for_model(
        obj,
        for_concrete_model=True,
    )

    cached = _find_valid_cached_translation(
        content_type=content_type,
        object_id=obj.pk,
        field_name=normalized_field_name,
        target_language=resolved_target_language,
        source_text_hash=source_text_hash,
        source_text=normalized_source_text,
        allow_humanize=should_humanize,
    )

    if cached is not None:
        return _translation_result_from_cache(
            cached
        )

    aws_result = _translate_paragraphs_with_aws(
        source_text=normalized_source_text,
        target_language=resolved_target_language,
        source_language=resolved_source_language,
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

    if should_humanize:
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
            logger.exception(
                "[translation] humanization failed "
                "object=%s.%s#%s field=%s "
                "source_language=%s target_language=%s",
                content_type.app_label,
                content_type.model,
                obj.pk,
                normalized_field_name,
                resolved_source_language,
                resolved_target_language,
            )

    cached, created = _create_translation_cache_safely(
        content_type=content_type,
        object_id=obj.pk,
        field_name=normalized_field_name,
        source_language=aws_result[
            "source_language"
        ],
        target_language=resolved_target_language,
        source_text_hash=source_text_hash,
        translated_text=final_text,
        engine=engine,
        is_humanized=is_humanized,
        llm_model=llm_model,
        prompt_version=prompt_version,
        humanized_at=humanized_at,
    )

    return {
        "text": cached.translated_text,
        "source_language": cached.source_language,
        "target_language": cached.target_language,
        "cached": not created,
        "engine": cached.engine,
        "is_humanized": cached.is_humanized,
        "llm_model": cached.llm_model,
        "prompt_version": cached.prompt_version,
        "cache_id": cached.pk,
    }

def translate_cached(
    *,
    obj,
    field_name: str,
    user=None,
    target_language: str | None = None,
    source_language: str | None = None,
    humanize: bool | None = None,
) -> dict:
    """
    Translate a real model text field.

    Existing callers remain backward-compatible.
    """

    raw_source_text = getattr(
        obj,
        field_name,
        None,
    )

    return translate_text_cached(
        obj=obj,
        field_name=field_name,
        source_text=raw_source_text,
        user=user,
        target_language=target_language,
        source_language=source_language,
        humanize=humanize,
    )
    

def update_cached_translation_humanization(
    *,
    obj,
    field_name: str,
    source_text,
    target_language: str,
    translated_text: str,
    llm_model: str,
    prompt_version: str,
) -> TranslationCache:
    """
    Update an existing exact cache row with a validated humanized value.
    """

    normalized_field_name = _normalize_cache_field_name(
        field_name
    )

    normalized_source_text = _normalize_source_text(
        source_text
    )

    normalized_translated_text = _normalize_source_text(
        translated_text
    )

    source_text_hash = hash_text(
        normalized_source_text
    )

    content_type = ContentType.objects.get_for_model(
        obj,
        for_concrete_model=True,
    )

    with transaction.atomic():
        cached = (
            TranslationCache.objects
            .select_for_update()
            .get(
                content_type=content_type,
                object_id=obj.pk,
                field_name=normalized_field_name,
                target_language=target_language,
                source_text_hash=source_text_hash,
            )
        )

        cached.translated_text = normalized_translated_text
        cached.engine = "aws+llm"
        cached.is_humanized = True
        cached.llm_model = str(
            llm_model or ""
        )[:50]
        cached.prompt_version = str(
            prompt_version or ""
        )[:20]
        cached.humanized_at = timezone.now()
        cached.last_accessed_at = timezone.now()

        cached.save(
            update_fields=[
                "translated_text",
                "engine",
                "is_humanized",
                "llm_model",
                "prompt_version",
                "humanized_at",
                "last_accessed_at",
            ]
        )

    return cached