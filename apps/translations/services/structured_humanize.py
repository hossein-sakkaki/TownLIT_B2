# apps/translations/services/structured_humanize.py

from __future__ import annotations

import json
from dataclasses import dataclass

from django.conf import settings
from openai import OpenAI

from apps.translations.services.language_hints import (
    get_language_hints,
)


@dataclass(frozen=True)
class StructuredHumanizeItem:
    key: str
    role: str
    source_text: str
    translated_text: str


def _extract_content(response) -> str:
    try:
        return str(
            response.choices[0].message.content or ""
        ).strip()
    except Exception:
        return ""


def _current_prompt_version() -> str:
    return str(
        getattr(
            settings,
            "TRANSLATIONS_STRUCTURED_PROMPT_VERSION",
            "structured-v1.0",
        )
        or "structured-v1.0"
    )[:20]


def _build_messages(
    *,
    items: list[StructuredHumanizeItem],
    target_language: str,
    context: str,
    instructions: list[str],
) -> list[dict]:
    language_hints = get_language_hints(
        target_language
    )

    system_prompt = (
        "You are a professional multilingual localization editor for a modern social application.\n\n"
        "You will receive a related set of source texts and existing machine translations. "
        "Treat the complete set as one coherent experience, not as unrelated strings.\n\n"
        "Your task:\n"
        "- Produce natural, clear, warm, contemporary localization\n"
        "- Use the source text as the authority for meaning\n"
        "- Use the current translation only as a draft that may be rewritten\n"
        "- Keep all items semantically consistent with each other\n"
        "- Preserve the exact key of every item\n"
        "- Return exactly one translated value for every supplied item\n\n"
        "Strict rules:\n"
        "- Do not add new facts, theology, advice, promises, or interpretations\n"
        "- Do not omit meaningful information\n"
        "- Avoid literal English sentence structure when unnatural in the target language\n"
        "- Avoid bureaucratic, academic, archaic, sermon-like, or machine-translated wording\n"
        "- Keep short interface choices concise\n"
        "- Preserve the role and grammatical perspective required by the context\n"
        "- Do not translate, modify, remove, or reorder keys\n"
        "- Return valid JSON only\n\n"
        "Required JSON format:\n"
        '{\n'
        '  "items": [\n'
        '    {"key": "exact_key", "text": "final localized text"}\n'
        "  ]\n"
        "}"
    )

    payload = {
        "target_language": target_language,
        "context": context,
        "instructions": instructions,
        "language_hints": language_hints,
        "items": [
            {
                "key": item.key,
                "role": item.role,
                "source_text": item.source_text,
                "current_translation": item.translated_text,
            }
            for item in items
        ],
    }

    user_prompt = (
        "Localize the following related text set as one coherent experience.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]


def _validate_output(
    *,
    raw_content: str,
    expected_items: list[StructuredHumanizeItem],
) -> dict[str, str]:
    if not raw_content:
        raise RuntimeError(
            "Structured humanization returned empty content."
        )

    try:
        payload = json.loads(
            raw_content
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Structured humanization returned invalid JSON."
        ) from exc

    raw_items = payload.get(
        "items"
    )

    if not isinstance(
        raw_items,
        list,
    ):
        raise RuntimeError(
            "Structured humanization response is missing items."
        )

    expected_keys = [
        item.key
        for item in expected_items
    ]

    translated_values: dict[str, str] = {}

    for raw_item in raw_items:
        if not isinstance(
            raw_item,
            dict,
        ):
            raise RuntimeError(
                "Structured humanization contains an invalid item."
            )

        key = str(
            raw_item.get("key")
            or ""
        ).strip()

        text = str(
            raw_item.get("text")
            or ""
        ).strip()

        if not key or not text:
            raise RuntimeError(
                "Structured humanization contains an empty key or text."
            )

        if key in translated_values:
            raise RuntimeError(
                f"Structured humanization returned duplicate key: {key}"
            )

        translated_values[
            key
        ] = text

    returned_keys = list(
        translated_values.keys()
    )

    if set(
        returned_keys
    ) != set(
        expected_keys
    ):
        missing = sorted(
            set(expected_keys)
            - set(returned_keys)
        )

        unexpected = sorted(
            set(returned_keys)
            - set(expected_keys)
        )

        raise RuntimeError(
            "Structured humanization key mismatch. "
            f"Missing={missing}, unexpected={unexpected}."
        )

    if len(
        returned_keys
    ) != len(
        expected_keys
    ):
        raise RuntimeError(
            "Structured humanization item count mismatch."
        )

    return translated_values


def humanize_structured_translation(
    *,
    items: list[StructuredHumanizeItem],
    target_language: str,
    context: str,
    instructions: list[str] | None = None,
) -> dict:
    """
    Humanize one related set in a single contextual request.
    """

    if not items:
        raise ValueError(
            "Structured humanization requires at least one item."
        )

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    model = settings.OPENAI_TRANSLATION_MODEL
    prompt_version = _current_prompt_version()

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY
    )

    response = client.chat.completions.create(
        model=model,
        messages=_build_messages(
            items=items,
            target_language=target_language,
            context=context,
            instructions=instructions or [],
        ),
        response_format={
            "type": "json_object",
        },
        temperature=0.25,
    )

    raw_content = _extract_content(
        response
    )

    values = _validate_output(
        raw_content=raw_content,
        expected_items=items,
    )

    return {
        "values": values,
        "model": model,
        "prompt_version": prompt_version,
    }