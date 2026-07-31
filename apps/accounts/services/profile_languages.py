#
#  apps/accounts/services/profile_languages.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-30.
#  Last Update by Hossein Sakkaki on 2026-07-30.
#


from __future__ import annotations

from functools import lru_cache
from typing import Any

from apps.profilesOrg.constants import LANGUAGE_CHOICES
from apps.translations.services.supported_languages import (
    get_supported_languages,
)


@lru_cache(maxsize=1)
def _translation_language_index() -> dict[str, dict[str, Any]]:
    """
    Index translation languages by normalized language code.
    """
    index: dict[str, dict[str, Any]] = {}

    for item in get_supported_languages():
        code = str(item.get("code") or "").strip()

        if not code:
            continue

        index[code.lower()] = item

    return index


def get_profile_language_codes() -> set[str]:
    """
    Return accepted profile language codes.
    """
    return {
        str(code).strip()
        for code, _ in LANGUAGE_CHOICES
        if str(code).strip()
    }


def get_profile_language_options() -> list[dict[str, Any]]:
    """
    Build the client-facing profile language list.

    LANGUAGE_CHOICES remains the profile source of truth.
    Translation support is returned only as metadata.
    """
    translation_index = _translation_language_index()
    options: list[dict[str, Any]] = []

    for code, name in LANGUAGE_CHOICES:
        normalized_code = str(code).strip()

        translation_item = translation_index.get(
            normalized_code.lower()
        )

        native_name = None
        translation_label = None

        if translation_item:
            native_name = (
                str(
                    translation_item.get("native")
                    or ""
                ).strip()
                or None
            )

            translation_label = (
                str(
                    translation_item.get("label")
                    or ""
                ).strip()
                or None
            )

        options.append({
            "code": normalized_code,
            "name": str(name).strip(),
            "native_name": native_name,
            "display_label": translation_label,
            "translation_supported": bool(
                translation_item
            ),
        })

    return options