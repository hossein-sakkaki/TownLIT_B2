# apps/journey_insights/services/daily_prompt_localization.py

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from apps.translations.services.language import (
    DEFAULT_SOURCE_LANGUAGE,
)
from apps.translations.services.structured_text import (
    StructuredTranslationItem,
    translate_structured_texts_for_user,
)


logger = logging.getLogger(
    __name__
)


@dataclass(frozen=True)
class LocalizedDailyReflectionContent:
    prompt: str
    choices: list[dict]
    source_language: str
    display_language: str
    is_translated: bool
    all_cached: bool


def _choice_display_key(
    choice: dict,
) -> str | None:
    """
    Find the visible text field of a choice snapshot.
    """

    for key in (
        "label",
        "text",
        "title",
        "value",
    ):
        value = choice.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value.strip():
            return key

    return None


def _safe_cache_suffix(
    value,
) -> str:
    """
    Build a cache-safe field suffix.
    """

    cleaned = str(
        value or ""
    ).strip().lower()

    cleaned = re.sub(
        r"[^a-z0-9_-]+",
        "-",
        cleaned,
    ).strip("-")

    return cleaned[:32]


def _choice_cache_key(
    *,
    choice: dict,
    position: int,
) -> str:
    """
    Build a stable cache key for one choice.
    """

    for key in (
        "code",
        "public_id",
        "id",
    ):
        suffix = _safe_cache_suffix(
            choice.get(
                key
            )
        )

        if suffix:
            return f"choice:{suffix}"

    return f"choice:position-{position}"


def localize_daily_reflection_content(
    *,
    user,
    question,
    prompt_snapshot: str,
    choice_snapshot: list[dict] | None,
) -> LocalizedDailyReflectionContent:
    """
    Localize a Daily Reflection question and all choices together.
    """

    original_prompt = str(
        prompt_snapshot or ""
    )

    original_choices = [
        dict(choice)
        for choice in (
            choice_snapshot or []
        )
    ]

    items = [
        StructuredTranslationItem(
            key="prompt",
            text=original_prompt,
            role="reflection_question",
        )
    ]

    choice_bindings: list[
        tuple[int, str, str]
    ] = []

    for position, choice in enumerate(
        original_choices
    ):
        display_key = _choice_display_key(
            choice
        )

        if display_key is None:
            continue

        cache_key = _choice_cache_key(
            choice=choice,
            position=position,
        )

        items.append(
            StructuredTranslationItem(
                key=cache_key,
                text=str(
                    choice.get(
                        display_key
                    )
                    or ""
                ),
                role="reflection_choice",
            )
        )

        choice_bindings.append(
            (
                position,
                display_key,
                cache_key,
            )
        )

    try:
        result = translate_structured_texts_for_user(
            cache_object=question,
            items=items,
            user=user,
            source_language=DEFAULT_SOURCE_LANGUAGE,
            fallback_language=DEFAULT_SOURCE_LANGUAGE,
            context=(
                "A private daily reflection question shown before a user "
                "creates a Journey entry in TownLIT. The question and all "
                "choices must read as one coherent, warm, understandable set."
            ),
            instructions=[
                (
                    "Translate the question and all answer choices together, "
                    "using one consistent tone and grammatical perspective."
                ),
                (
                    "Use natural, contemporary language suitable for an app, "
                    "not literal or formal machine-translation wording."
                ),
                (
                    "Keep the question warm, concise, direct, and easy to understand."
                ),
                (
                    "Write answer choices as personal actions or commitments "
                    "from the user's perspective when the source expresses "
                    "first-person action."
                ),
                (
                    "Keep all choices parallel in grammar, tone, tense, and perspective."
                ),
                (
                    "Do not convert answer choices into commands directed at the user "
                    "unless the source itself is clearly imperative."
                ),
                (
                    "Keep each choice concise enough to work as a selectable radio option."
                ),
                (
                    "Preserve the exact meaning and distinction of every choice."
                ),
            ],
        )

    except Exception:
        logger.exception(
            "[daily-reflection] automatic localization failed "
            "question_id=%s user_id=%s",
            getattr(
                question,
                "pk",
                None,
            ),
            getattr(
                user,
                "pk",
                None,
            ),
        )

        return LocalizedDailyReflectionContent(
            prompt=original_prompt,
            choices=original_choices,
            source_language=DEFAULT_SOURCE_LANGUAGE,
            display_language=DEFAULT_SOURCE_LANGUAGE,
            is_translated=False,
            all_cached=False,
        )

    localized_choices = [
        dict(choice)
        for choice in original_choices
    ]

    for (
        position,
        display_key,
        cache_key,
    ) in choice_bindings:
        translated_text = result.values.get(
            cache_key
        )

        if translated_text:
            localized_choices[
                position
            ][
                display_key
            ] = translated_text

    return LocalizedDailyReflectionContent(
        prompt=(
            result.values.get(
                "prompt"
            )
            or original_prompt
        ),
        choices=localized_choices,
        source_language=result.source_language,
        display_language=result.display_language,
        is_translated=result.is_translated,
        all_cached=result.all_cached,
    )