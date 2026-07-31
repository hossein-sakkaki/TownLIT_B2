# apps/creative_editor/services/document.py

from __future__ import annotations

import uuid

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import (
    ValidationError,
)

from apps.creative_editor.models import (
    CreativeFont,
    StickerAsset,
)
from apps.creative_editor.validators.document import (
    validate_creative_document,
)


@dataclass(frozen=True)
class CreativeDocumentReferences:
    """
    Resolved references used by one document.
    """

    font_keys: frozenset[str]
    sticker_public_ids: frozenset[str]


def extract_document_references(
    document: dict[str, Any],
) -> CreativeDocumentReferences:
    """
    Extract normalized document references.
    """

    font_keys: set[str] = set()
    sticker_public_ids: set[str] = set()

    layers = document.get(
        "layers"
    ) or []

    if not isinstance(
        layers,
        list,
    ):
        return CreativeDocumentReferences(
            font_keys=frozenset(),
            sticker_public_ids=frozenset(),
        )

    for layer in layers:
        if not isinstance(
            layer,
            dict,
        ):
            continue

        layer_type = layer.get(
            "type"
        )

        content = layer.get(
            "content"
        )

        if not isinstance(
            content,
            dict,
        ):
            continue

        if layer_type == "text":
            font_key = str(
                content.get(
                    "font_key"
                )
                or ""
            ).strip()

            if font_key:
                font_keys.add(
                    font_key
                )

        elif layer_type == "sticker":
            raw_sticker_id = str(
                content.get(
                    "sticker_id"
                )
                or ""
            ).strip()

            if not raw_sticker_id:
                continue

            try:
                sticker_id = str(
                    uuid.UUID(
                        raw_sticker_id
                    )
                )
            except (
                TypeError,
                ValueError,
                AttributeError,
            ):
                # Schema validation reports
                # the invalid UUID.
                sticker_id = (
                    raw_sticker_id.lower()
                )

            sticker_public_ids.add(
                sticker_id
            )

    return CreativeDocumentReferences(
        font_keys=frozenset(
            font_keys
        ),
        sticker_public_ids=frozenset(
            sticker_public_ids
        ),
    )


def validate_document_references(
    document: dict[str, Any],
) -> CreativeDocumentReferences:
    """
    Validate schema and database references.
    """

    validate_creative_document(
        document
    )

    references = (
        extract_document_references(
            document
        )
    )

    _validate_font_references(
        references.font_keys
    )

    _validate_sticker_references(
        references.sticker_public_ids
    )

    return references


def _validate_font_references(
    font_keys: frozenset[str],
) -> None:
    """
    Ensure every referenced font is active.
    """

    if not font_keys:
        return

    available_keys = set(
        CreativeFont.objects
        .filter(
            key__in=font_keys,
            is_active=True,
        )
        .values_list(
            "key",
            flat=True,
        )
    )

    missing = sorted(
        set(font_keys)
        - available_keys
    )

    if missing:
        raise ValidationError(
            {
                "document": [
                    (
                        "Unknown or inactive font keys: "
                        + ", ".join(
                            missing
                        )
                    )
                ],
            }
        )


def _validate_sticker_references(
    sticker_public_ids: frozenset[str],
) -> None:
    """
    Ensure every sticker is active and ready.
    """

    if not sticker_public_ids:
        return

    normalized_ids: set[
        uuid.UUID
    ] = set()

    invalid_ids: list[str] = []

    for value in sticker_public_ids:
        try:
            normalized_ids.add(
                uuid.UUID(value)
            )
        except (
            TypeError,
            ValueError,
            AttributeError,
        ):
            invalid_ids.append(
                value
            )

    if invalid_ids:
        raise ValidationError(
            {
                "document": [
                    (
                        "Invalid sticker identifiers: "
                        + ", ".join(
                            sorted(
                                invalid_ids
                            )
                        )
                    )
                ],
            }
        )

    available_ids = {
        str(value)
        for value in (
            StickerAsset.objects
            .filter(
                public_id__in=(
                    normalized_ids
                ),
                is_active=True,
                is_converted=True,
                pack__is_active=True,
            )
            .values_list(
                "public_id",
                flat=True,
            )
        )
    }

    missing = sorted(
        str(value)
        for value in normalized_ids
        if str(value) not in available_ids
    )

    if missing:
        raise ValidationError(
            {
                "document": [
                    (
                        "Unknown or unavailable stickers: "
                        + ", ".join(
                            missing
                        )
                    )
                ],
            }
        )