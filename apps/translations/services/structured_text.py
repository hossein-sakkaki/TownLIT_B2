# apps/translations/services/structured_text.py

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from apps.translations.services.base import (
    humanize_enabled,
    translate_text_cached,
    update_cached_translation_humanization,
)
from apps.translations.services.language import (
    DEFAULT_SOURCE_LANGUAGE,
    language_codes_match,
    resolve_user_primary_language,
)
from apps.translations.services.structured_humanize import (
    StructuredHumanizeItem,
    humanize_structured_translation,
)


logger = logging.getLogger(
    __name__
)


@dataclass(frozen=True)
class StructuredTranslationItem:
    key: str
    text: str
    role: str = "text"


@dataclass(frozen=True)
class StructuredTranslationResult:
    values: dict[str, str]
    source_language: str
    display_language: str
    is_translated: bool
    all_cached: bool


def _structured_prompt_version() -> str:
    return str(
        getattr(
            settings,
            "TRANSLATIONS_STRUCTURED_PROMPT_VERSION",
            "structured-v1.0",
        )
        or "structured-v1.0"
    )[:20]


def translate_structured_texts_for_user(
    *,
    cache_object,
    items: list[StructuredTranslationItem],
    user,
    source_language: str = DEFAULT_SOURCE_LANGUAGE,
    fallback_language: str = DEFAULT_SOURCE_LANGUAGE,
    context: str = "Related application interface texts.",
    instructions: list[str] | None = None,
) -> StructuredTranslationResult:
    """
    Translate and humanize a related text set as one coherent experience.

    Every item still uses its own TranslationCache row.
    """

    if not items:
        return StructuredTranslationResult(
            values={},
            source_language=source_language,
            display_language=source_language,
            is_translated=False,
            all_cached=True,
        )

    keys = [
        item.key
        for item in items
    ]

    if len(
        keys
    ) != len(
        set(keys)
    ):
        raise ValueError(
            "Structured translation item keys must be unique."
        )

    original_values = {
        item.key: str(
            item.text or ""
        )
        for item in items
    }

    target_language = resolve_user_primary_language(
        user=user,
        fallback_language=fallback_language,
    )

    if language_codes_match(
        source_language,
        target_language,
    ):
        return StructuredTranslationResult(
            values=original_values,
            source_language=source_language,
            display_language=source_language,
            is_translated=False,
            all_cached=True,
        )

    base_values: dict[str, str] = {}
    base_results: dict[str, dict] = {}

    for item in items:
        source_text = str(
            item.text or ""
        ).strip()

        if not source_text:
            base_values[
                item.key
            ] = ""

            base_results[
                item.key
            ] = {
                "cached": True,
                "is_humanized": False,
                "prompt_version": "",
            }

            continue

        result = translate_text_cached(
            obj=cache_object,
            field_name=item.key,
            source_text=source_text,
            user=user,
            target_language=target_language,
            source_language=source_language,
            humanize=False,
        )

        base_values[
            item.key
        ] = str(
            result.get("text")
            or source_text
        )

        base_results[
            item.key
        ] = result

    expected_prompt_version = (
        _structured_prompt_version()
    )

    nonempty_items = [
        item
        for item in items
        if str(
            item.text or ""
        ).strip()
    ]

    all_structured_cached = bool(
        nonempty_items
    ) and all(
        bool(
            base_results[
                item.key
            ].get(
                "is_humanized"
            )
        )
        and str(
            base_results[
                item.key
            ].get(
                "prompt_version"
            )
            or ""
        )
        == expected_prompt_version
        for item in nonempty_items
    )

    if (
        not humanize_enabled()
        or all_structured_cached
    ):
        return StructuredTranslationResult(
            values=base_values,
            source_language=source_language,
            display_language=target_language,
            is_translated=True,
            all_cached=all_structured_cached,
        )

    structured_items = [
        StructuredHumanizeItem(
            key=item.key,
            role=item.role,
            source_text=str(
                item.text or ""
            ).strip(),
            translated_text=base_values[
                item.key
            ],
        )
        for item in nonempty_items
    ]

    try:
        humanized = humanize_structured_translation(
            items=structured_items,
            target_language=target_language,
            context=context,
            instructions=instructions or [],
        )

        final_values = dict(
            base_values
        )

        for item in nonempty_items:
            final_text = str(
                humanized[
                    "values"
                ].get(
                    item.key
                )
                or ""
            ).strip()

            if not final_text:
                raise RuntimeError(
                    f"Structured translation is empty for key: {item.key}"
                )

            update_cached_translation_humanization(
                obj=cache_object,
                field_name=item.key,
                source_text=item.text,
                target_language=target_language,
                translated_text=final_text,
                llm_model=humanized[
                    "model"
                ],
                prompt_version=humanized[
                    "prompt_version"
                ],
            )

            final_values[
                item.key
            ] = final_text

        return StructuredTranslationResult(
            values=final_values,
            source_language=source_language,
            display_language=target_language,
            is_translated=True,
            all_cached=False,
        )

    except Exception:
        logger.exception(
            "[translation] structured humanization failed "
            "object=%s#%s target_language=%s keys=%s",
            cache_object.__class__.__name__,
            getattr(
                cache_object,
                "pk",
                None,
            ),
            target_language,
            keys,
        )

        return StructuredTranslationResult(
            values=base_values,
            source_language=source_language,
            display_language=target_language,
            is_translated=True,
            all_cached=False,
        )