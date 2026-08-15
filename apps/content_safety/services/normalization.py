# apps/content_safety/services/normalization.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from __future__ import annotations

import re
import unicodedata


_SPACE_RUN_RE = re.compile(
    r"[ \t]+"
)

_NEWLINE_RUN_RE = re.compile(
    r"\n{3,}"
)


def _normalize_line_endings(
    value: str,
) -> str:
    return (
        value
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _remove_format_controls(
    value: str,
) -> str:
    """
    Remove invisible controls from inspection text.
    """

    return "".join(
        char
        for char in value
        if unicodedata.category(char) != "Cf"
    )


def normalize_text_for_safety(
    value,
) -> str:
    """
    Build canonical inspection text.
    """

    if value is None:
        return ""

    text = str(
        value
    )

    text = _normalize_line_endings(
        text
    )

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = _remove_format_controls(
        text
    )

    text = _SPACE_RUN_RE.sub(
        " ",
        text,
    )

    text = _NEWLINE_RUN_RE.sub(
        "\n\n",
        text,
    )

    return text.strip()