# apps/creative_editor/services/emoji_text.py

from __future__ import annotations

import unicodedata

from dataclasses import dataclass

import regex


EMOJI_PRESENTATION_SELECTOR = "\uFE0F"
TEXT_PRESENTATION_SELECTOR = "\uFE0E"
ZERO_WIDTH_JOINER = "\u200D"
KEYCAP = "\u20E3"


@dataclass(frozen=True)
class CreativeTextCluster:
    """
    One user-perceived Unicode grapheme cluster.
    """

    text: str
    is_emoji: bool


def split_grapheme_clusters(
    value: str,
) -> list[str]:
    """
    Split text into Unicode extended grapheme clusters.
    """

    return regex.findall(
        r"\X",
        str(value or ""),
    )


def is_emoji_cluster(
    cluster: str,
) -> bool:
    """
    Detect whether a grapheme cluster requires Emoji
    presentation.

    The test intentionally preserves complete ZWJ,
    skin-tone, flag, keycap and variation-selector
    sequences.
    """

    if not cluster:
        return False

    if EMOJI_PRESENTATION_SELECTOR in cluster:
        return True

    if ZERO_WIDTH_JOINER in cluster:
        return True

    if KEYCAP in cluster:
        return True

    regional_indicators = [
        character
        for character in cluster
        if 0x1F1E6 <= ord(character) <= 0x1F1FF
    ]

    if len(regional_indicators) >= 2:
        return True

    for character in cluster:
        codepoint = ord(character)

        if 0x1F3FB <= codepoint <= 0x1F3FF:
            return True

        if (
            0x1F000 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x26FF
            or 0x2700 <= codepoint <= 0x27BF
        ):
            return True

        name = unicodedata.name(
            character,
            "",
        )

        if "EMOJI" in name:
            return True

    return False


def build_text_clusters(
    value: str,
) -> list[CreativeTextCluster]:
    """
    Build classified grapheme clusters.
    """

    return [
        CreativeTextCluster(
            text=cluster,
            is_emoji=is_emoji_cluster(
                cluster
            ),
        )
        for cluster in split_grapheme_clusters(
            value
        )
    ]