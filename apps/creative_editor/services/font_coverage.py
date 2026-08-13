# apps/creative_editor/services/font_coverage.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-10.
# Last Update by Hossein Sakkaki on 2026-08-10.

from __future__ import annotations

import unicodedata

from functools import lru_cache

from fontTools.ttLib import TTFont

from apps.creative_editor.models.font import CreativeFont
from apps.creative_editor.services.font_resolver import (
    CreativeFontError,
    default_font_key,
    resolve_font_asset,
)


class CreativeFontCoverageError(CreativeFontError):
    """
    Raised when no active bundled font can render text safely.
    """


@lru_cache(maxsize=256)
def _font_codepoints(
    font_key: str,
) -> frozenset[int]:
    """
    Return Unicode codepoints exposed by the font's best cmap.
    """

    asset = resolve_font_asset(
        font_key
    )

    font = TTFont(
        asset.path,
        lazy=True,
    )

    try:
        cmap = font.getBestCmap()

        if not cmap:
            return frozenset()

        return frozenset(
            cmap.keys()
        )
    finally:
        font.close()


def _requires_creative_glyph(
    character: str,
) -> bool:
    """
    Ignore text controls, variation selectors and Emoji.
    """

    if not character:
        return False

    if character.isspace():
        return False

    codepoint = ord(
        character
    )

    category = unicodedata.category(
        character
    )

    if category in {
        "Cc",
        "Cf",
    }:
        return False

    if (
        0xFE00 <= codepoint <= 0xFE0F
        or 0xE0100 <= codepoint <= 0xE01EF
    ):
        return False

    if _is_emoji_codepoint(
        codepoint
    ):
        return False

    return True


def _is_emoji_codepoint(
    codepoint: int,
) -> bool:
    """
    Emoji is handled by the dedicated Emoji renderer.
    """

    return (
        0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or 0x2300 <= codepoint <= 0x23FF
    )


def required_text_codepoints(
    text: str,
) -> frozenset[int]:
    return frozenset(
        ord(character)
        for character in str(
            text or ""
        )
        if _requires_creative_glyph(
            character
        )
    )


def font_supports_text(
    *,
    font_key: str,
    text: str,
) -> bool:
    """
    Return True when one bundled font covers the text.
    """

    required = required_text_codepoints(
        text
    )

    if not required:
        return True

    available = _font_codepoints(
        font_key
    )

    return required.issubset(
        available
    )


def missing_text_codepoints(
    *,
    font_key: str,
    text: str,
) -> frozenset[int]:
    required = required_text_codepoints(
        text
    )

    if not required:
        return frozenset()

    return required.difference(
        _font_codepoints(
            font_key
        )
    )


def resolve_user_selectable_font_key(
    *,
    text: str,
    preferred_font_key: str | None = None,
) -> str:
    """
    Resolve a font suitable for becoming document.font_key.

    Hidden fallback fonts are intentionally excluded.
    """

    return _resolve_compatible_font_key(
        text=text,
        preferred_font_key=preferred_font_key,
        include_hidden_fallbacks=False,
    )


def resolve_compatible_font_key(
    *,
    text: str,
    preferred_font_key: str | None = None,
) -> str:
    """
    Resolve a bundled rendering font.

    Hidden fallback fonts are included. This function is
    intended for backend render runs, not Font Picker state.
    """

    return _resolve_compatible_font_key(
        text=text,
        preferred_font_key=preferred_font_key,
        include_hidden_fallbacks=True,
    )


def _resolve_compatible_font_key(
    *,
    text: str,
    preferred_font_key: str | None,
    include_hidden_fallbacks: bool,
) -> str:
    normalized_text = str(
        text or ""
    )

    preferred = str(
        preferred_font_key or ""
    ).strip()

    base_queryset = CreativeFont.objects.filter(
        is_active=True,
        source=CreativeFont.Source.BUNDLED,
    )

    candidates: list[str] = []

    # 1. Preserve the user's selected font when possible.
    if preferred:
        preferred_exists = base_queryset.filter(
            key=preferred
        ).exists()

        if preferred_exists:
            candidates.append(
                preferred
            )

    if include_hidden_fallbacks:
        # 2. Prefer neutral hidden fallback fonts.
        fallback_keys = (
            base_queryset
            .filter(
                is_user_selectable=False,
            )
            .order_by(
                "sort_order",
                "display_name",
                "id",
            )
            .values_list(
                "key",
                flat=True,
            )
        )

        for key in fallback_keys:
            if key not in candidates:
                candidates.append(
                    key
                )

        # 3. Configured default remains a final normal fallback.
        configured_default = default_font_key()

        if (
            base_queryset.filter(
                key=configured_default
            ).exists()
            and configured_default not in candidates
        ):
            candidates.append(
                configured_default
            )

        # 4. Other selectable fonts are the last resort.
        selectable_keys = (
            base_queryset
            .filter(
                is_user_selectable=True,
            )
            .order_by(
                "sort_order",
                "display_name",
                "id",
            )
            .values_list(
                "key",
                flat=True,
            )
        )

        for key in selectable_keys:
            if key not in candidates:
                candidates.append(
                    key
                )

    else:
        # Document-level font selection must never choose hidden fonts.
        selectable_queryset = base_queryset.filter(
            is_user_selectable=True,
        )

        available_keys = set(
            selectable_queryset.values_list(
                "key",
                flat=True,
            )
        )

        candidates = [
            key
            for key in candidates
            if key in available_keys
        ]

        configured_default = default_font_key()

        if (
            configured_default in available_keys
            and configured_default not in candidates
        ):
            candidates.append(
                configured_default
            )

        selectable_keys = (
            selectable_queryset
            .order_by(
                "sort_order",
                "display_name",
                "id",
            )
            .values_list(
                "key",
                flat=True,
            )
        )

        for key in selectable_keys:
            if key not in candidates:
                candidates.append(
                    key
                )

    for key in candidates:
        try:
            if font_supports_text(
                font_key=key,
                text=normalized_text,
            ):
                return key
        except CreativeFontError:
            continue

    required = sorted(
        required_text_codepoints(
            normalized_text
        )
    )

    formatted = ", ".join(
        f"U+{value:04X}"
        for value in required[:16]
    )

    scope = (
        "active bundled TownLIT font"
        if include_hidden_fallbacks
        else "user-selectable TownLIT font"
    )

    raise CreativeFontCoverageError(
        (
            f"No {scope} can render the supplied text. "
            f"Required codepoints: {formatted}"
        )
    )

def clear_font_coverage_caches() -> None:
    _font_codepoints.cache_clear()