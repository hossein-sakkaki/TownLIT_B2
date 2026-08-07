# apps/creative_editor/services/font_resolver.py

from __future__ import annotations

import hashlib
import logging
import os

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from PIL import ImageFont

from apps.creative_editor.models.font import (
    CreativeFont,
)


logger = logging.getLogger(__name__)


class CreativeFontError(Exception):
    """
    Raised when a creative font cannot be resolved safely.
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
    """

    path: str
    requested_size: int
    loaded_size: int
    font: ImageFont.FreeTypeFont


@dataclass(frozen=True)
class CreativeFontAsset:
    """
    Immutable bundled font asset.
    """

    key: str
    filename: str
    path: str
    postscript_name: str
    version: str
    sha256: str


def creative_font_directory() -> Path:
    """
    Return the authoritative bundled font directory.
    """

    configured = str(
        getattr(
            settings,
            "CREATIVE_EDITOR_FONT_DIR",
            "",
        )
        or ""
    ).strip()

    if not configured:
        raise CreativeFontError(
            "CREATIVE_EDITOR_FONT_DIR is not configured."
        )

    directory = Path(
        configured
    ).resolve()

    if not directory.is_dir():
        raise CreativeFontError(
            (
                "Creative font directory does not exist: "
                f"{directory}"
            )
        )

    return directory


def default_font_key() -> str:
    """
    Return the authoritative default Creative Editor font key.
    """

    value = str(
        getattr(
            settings,
            "CREATIVE_EDITOR_DEFAULT_FONT_KEY",
            "",
        )
        or ""
    ).strip()

    if not value:
        raise CreativeFontError(
            (
                "CREATIVE_EDITOR_DEFAULT_FONT_KEY "
                "is not configured."
            )
        )

    return value


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


def _file_sha256(
    path: str,
) -> str:
    """
    Calculate SHA-256 for one font binary.
    """

    digest = hashlib.sha256()

    with open(
        path,
        "rb",
    ) as file_obj:
        for chunk in iter(
            lambda: file_obj.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


@lru_cache(maxsize=128)
def resolve_font_asset(
    font_key: str,
) -> CreativeFontAsset:
    """
    Resolve and verify one authoritative bundled font.
    """

    normalized_key = str(
        font_key
        or default_font_key()
    ).strip()

    if not normalized_key:
        raise CreativeFontError(
            "Creative font key is empty."
        )

    try:
        font_record = (
            CreativeFont.objects
            .only(
                "key",
                "binary_filename",
                "postscript_name",
                "asset_version",
                "asset_sha256",
                "is_active",
                "source",
            )
            .get(
                key=normalized_key,
                is_active=True,
            )
        )

    except CreativeFont.DoesNotExist as exc:
        raise CreativeFontError(
            (
                "No active creative font exists "
                f"for '{normalized_key}'."
            )
        ) from exc

    if (
        font_record.source
        != CreativeFont.Source.BUNDLED
    ):
        raise CreativeFontError(
            (
                "Creative renderer requires a bundled "
                f"font asset for '{normalized_key}'."
            )
        )

    filename = str(
        font_record.binary_filename
        or ""
    ).strip()

    if not filename:
        raise CreativeFontError(
            (
                "Creative font has no binary filename: "
                f"{normalized_key}"
            )
        )

    if (
        os.path.basename(
            filename
        )
        != filename
    ):
        raise CreativeFontError(
            (
                "Creative font filename is unsafe: "
                f"{normalized_key}"
            )
        )

    directory = creative_font_directory()

    path = (
        directory
        / filename
    ).resolve()

    try:
        path.relative_to(
            directory
        )

    except ValueError as exc:
        raise CreativeFontError(
            (
                "Creative font resolved outside "
                "the configured font directory."
            )
        ) from exc

    if not path.is_file():
        raise CreativeFontError(
            (
                "Creative font binary is unavailable: "
                f"{path}"
            )
        )

    expected_sha256 = str(
        font_record.asset_sha256
        or ""
    ).strip().lower()

    if not expected_sha256:
        raise CreativeFontError(
            (
                "Creative font is missing SHA-256: "
                f"{normalized_key}"
            )
        )

    actual_sha256 = _file_sha256(
        str(path)
    )

    if actual_sha256 != expected_sha256:
        raise CreativeFontError(
            (
                "Creative font checksum mismatch "
                f"for '{normalized_key}'. "
                f"expected={expected_sha256} "
                f"actual={actual_sha256}"
            )
        )

    return CreativeFontAsset(
        key=font_record.key,
        filename=filename,
        path=str(path),
        postscript_name=str(
            font_record.postscript_name
            or ""
        ).strip(),
        version=str(
            font_record.asset_version
            or ""
        ).strip(),
        sha256=actual_sha256,
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
    Load one verified creative font.
    """

    safe_size = max(
        8,
        min(
            512,
            int(
                round(
                    float(size)
                )
            ),
        ),
    )

    asset = resolve_font_asset(
        font_key
    )

    try:
        font = _load_cached_font(
            asset.path,
            safe_size,
        )

    except Exception as exc:
        raise CreativeFontError(
            (
                "Could not load creative font "
                f"'{asset.key}'."
            )
        ) from exc

    return ResolvedCreativeFont(
        key=asset.key,
        path=asset.path,
        size=safe_size,
        font=font,
    )


@lru_cache(maxsize=64)
def _load_cached_emoji_font(
    path: str,
    requested_size: int,
) -> tuple[
    int,
    ImageFont.FreeTypeFont,
]:
    """
    Load a color Emoji font.
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
            min(
                512,
                int(value),
            ),
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

            return (
                candidate_size,
                font,
            )

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
            int(
                round(
                    float(size)
                )
            ),
        ),
    )

    path = emoji_font_path()

    if (
        not path
        or not os.path.isfile(
            path
        )
    ):
        raise CreativeFontError(
            (
                "No server Emoji font file is available. "
                "Configure CREATIVE_EDITOR_EMOJI_FONT_FILE."
            )
        )

    loaded_size, font = (
        _load_cached_emoji_font(
            path,
            requested_size,
        )
    )

    return ResolvedCreativeEmojiFont(
        path=path,
        requested_size=requested_size,
        loaded_size=loaded_size,
        font=font,
    )


def clear_font_caches() -> None:
    """
    Clear cached creative font resources.
    """

    resolve_font_asset.cache_clear()
    _load_cached_font.cache_clear()
    _load_cached_emoji_font.cache_clear()