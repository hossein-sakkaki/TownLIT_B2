# apps/creative_editor/services/font_resolver.py

from __future__ import annotations

import logging
import os

from dataclasses import dataclass
from functools import lru_cache

from django.conf import settings

from PIL import ImageFont

from apps.creative_editor.constants import (
    CREATIVE_RENDER_DEFAULT_FONT_KEY,
)


logger = logging.getLogger(__name__)


class CreativeFontError(Exception):
    """
    Raised when no server font can be loaded.
    """


@dataclass(frozen=True)
class ResolvedCreativeFont:
    """
    One resolved server font.
    """

    key: str
    path: str
    size: int
    font: ImageFont.FreeTypeFont


@dataclass(frozen=True)
class ResolvedCreativeEmojiFont:
    """
    One resolved server Emoji font.

    Color Emoji fonts may expose fixed bitmap strikes,
    so the loaded size can differ from the requested
    text size.
    """

    path: str
    requested_size: int
    loaded_size: int
    font: ImageFont.FreeTypeFont


def creative_font_map() -> dict[str, str]:
    """
    Read configured font files.
    """

    configured = getattr(
        settings,
        "CREATIVE_EDITOR_FONT_FILES",
        {},
    )

    if not isinstance(configured, dict):
        return {}

    return {
        str(key).strip(): str(path).strip()
        for key, path in configured.items()
        if str(key).strip() and str(path).strip()
    }


def default_font_path() -> str:
    """
    Read the fallback font path.
    """

    return str(
        getattr(
            settings,
            "CREATIVE_EDITOR_DEFAULT_FONT_FILE",
            "",
        )
        or ""
    ).strip()


def emoji_font_path() -> str:
    """
    Read the configured Emoji font path.
    """

    return str(
        getattr(
            settings,
            "CREATIVE_EDITOR_EMOJI_FONT_FILE",
            "",
        )
        or ""
    ).strip()


@lru_cache(maxsize=64)
def resolve_font_path(
    font_key: str,
) -> tuple[str, str]:
    """
    Resolve one font key.
    """

    normalized_key = str(
        font_key
        or CREATIVE_RENDER_DEFAULT_FONT_KEY
    ).strip()

    path = creative_font_map().get(
        normalized_key
    )

    if path and os.path.isfile(path):
        return normalized_key, path

    fallback = default_font_path()

    if fallback and os.path.isfile(fallback):
        logger.warning(
            "creative_editor.font.fallback",
            extra={
                "font_key": normalized_key,
                "fallback": fallback,
            },
        )

        return (
            CREATIVE_RENDER_DEFAULT_FONT_KEY,
            fallback,
        )

    raise CreativeFontError(
        (
            "No server font file is available "
            f"for '{normalized_key}'."
        )
    )


@lru_cache(maxsize=256)
def _load_cached_font(
    path: str,
    size: int,
) -> ImageFont.FreeTypeFont:
    """
    Cache immutable FreeType fonts.
    """

    return ImageFont.truetype(
        path,
        size,
    )


def load_creative_font(
    *,
    font_key: str,
    size: int | float,
) -> ResolvedCreativeFont:
    """
    Load one cached renderer font.
    """

    safe_size = max(
        8,
        min(
            512,
            int(round(float(size))),
        ),
    )

    resolved_key, path = resolve_font_path(
        font_key
    )

    try:
        font = _load_cached_font(
            path,
            safe_size,
        )

    except Exception as exc:
        raise CreativeFontError(
            (
                "Could not load server font "
                f"'{resolved_key}'."
            )
        ) from exc

    return ResolvedCreativeFont(
        key=resolved_key,
        path=path,
        size=safe_size,
        font=font,
    )


@lru_cache(maxsize=64)
def _load_cached_emoji_font(
    path: str,
    requested_size: int,
) -> tuple[int, ImageFont.FreeTypeFont]:
    """
    Load a color Emoji font.

    Noto Color Emoji can expose fixed bitmap strikes.
    Try the requested size first, then known compatible
    strike sizes.
    """

    candidate_sizes = []

    for value in (
        requested_size,
        109,
        128,
        96,
        72,
        64,
        48,
        32,
    ):
        normalized = max(
            8,
            min(512, int(value)),
        )

        if normalized not in candidate_sizes:
            candidate_sizes.append(
                normalized
            )

    last_error: Exception | None = None

    for candidate_size in candidate_sizes:
        try:
            font = ImageFont.truetype(
                path,
                candidate_size,
            )

            return candidate_size, font

        except Exception as exc:
            last_error = exc

    raise CreativeFontError(
        "Could not load the configured Emoji font."
    ) from last_error


def load_creative_emoji_font(
    *,
    size: int | float,
) -> ResolvedCreativeEmojiFont:
    """
    Load the configured Emoji renderer font.
    """

    requested_size = max(
        8,
        min(
            512,
            int(round(float(size))),
        ),
    )

    path = emoji_font_path()

    if not path or not os.path.isfile(path):
        raise CreativeFontError(
            (
                "No server Emoji font file is available. "
                "Configure CREATIVE_EDITOR_EMOJI_FONT_FILE."
            )
        )

    loaded_size, font = _load_cached_emoji_font(
        path,
        requested_size,
    )

    return ResolvedCreativeEmojiFont(
        path=path,
        requested_size=requested_size,
        loaded_size=loaded_size,
        font=font,
    )


def clear_font_caches() -> None:
    """
    Clear font caches after config changes.
    """

    resolve_font_path.cache_clear()
    _load_cached_font.cache_clear()
    _load_cached_emoji_font.cache_clear()