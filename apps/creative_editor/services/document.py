# apps/creative_editor/services/document.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-07-21.
# Last Update by Hossein Sakkaki on 2026-08-10.
#

from __future__ import annotations

import uuid

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

from apps.creative_editor.models import (
    CreativeCompositionMedia,
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
    image_media_public_ids: frozenset[str]
    video_media_public_ids: frozenset[str]

    @property
    def media_public_ids(self) -> frozenset[str]:
        return frozenset(
            set(self.image_media_public_ids)
            | set(self.video_media_public_ids)
        )


def extract_document_references(
    document: dict[str, Any],
) -> CreativeDocumentReferences:
    """
    Extract normalized document references.
    """

    font_keys: set[str] = set()
    sticker_public_ids: set[str] = set()    
    image_media_public_ids: set[str] = set()
    video_media_public_ids: set[str] = set()

    layers = document.get("layers") or []

    if not isinstance(layers, list):
        return CreativeDocumentReferences(
            font_keys=frozenset(),
            sticker_public_ids=frozenset(),
            image_media_public_ids=frozenset(),
            video_media_public_ids=frozenset(),
        )

    for layer in layers:
        if not isinstance(layer, dict):
            continue

        layer_type = layer.get("type")
        content = layer.get("content")

        if not isinstance(content, dict):
            continue

        if layer_type == "text":
            font_key = str(
                content.get("font_key") or ""
            ).strip()

            if font_key:
                font_keys.add(font_key)

        elif layer_type == "sticker":
            value = _normalize_uuid_reference(
                content.get("sticker_id")
            )

            if value:
                sticker_public_ids.add(value)

        elif layer_type == "image":
            value = _normalize_uuid_reference(
                content.get("media_id")
            )

            if value:
                image_media_public_ids.add(value)

        elif layer_type == "video":
            value = _normalize_uuid_reference(
                content.get("media_id")
            )

            if value:
                video_media_public_ids.add(value)

    return CreativeDocumentReferences(
        font_keys=frozenset(font_keys),
        sticker_public_ids=frozenset(
            sticker_public_ids
        ),
        image_media_public_ids=frozenset(
            image_media_public_ids
        ),
        video_media_public_ids=frozenset(
            video_media_public_ids
        ),
    )


def validate_document_references(
    document: dict[str, Any],
    *,
    composition=None,
    require_media_ready: bool = True,
) -> CreativeDocumentReferences:
    """
    Validate schema and database references.
    """

    validate_creative_document(document)

    references = extract_document_references(
        document
    )

    _validate_font_references(
        references.font_keys
    )

    _validate_sticker_references(
        references.sticker_public_ids
    )

    _validate_media_references(
        references,
        composition=composition,
        require_ready=require_media_ready,
    )

    return references


def _normalize_uuid_reference(
    value,
) -> str:
    raw = str(
        value or ""
    ).strip()

    if not raw:
        return ""

    try:
        return str(
            uuid.UUID(raw)
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        return raw.lower()


def _validate_font_references(
    font_keys: frozenset[str],
) -> None:
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
                        + ", ".join(missing)
                    ),
                ],
            }
        )


def _validate_sticker_references(
    sticker_public_ids: frozenset[str],
) -> None:
    if not sticker_public_ids:
        return

    normalized_ids: set[uuid.UUID] = set()
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
            invalid_ids.append(value)

    if invalid_ids:
        raise ValidationError(
            {
                "document": [
                    (
                        "Invalid sticker identifiers: "
                        + ", ".join(
                            sorted(invalid_ids)
                        )
                    ),
                ],
            }
        )

    available_ids = {
        str(value)
        for value in (
            StickerAsset.objects
            .filter(
                public_id__in=normalized_ids,
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
                        + ", ".join(missing)
                    ),
                ],
            }
        )


def _validate_media_references(
    references: CreativeDocumentReferences,
    *,
    composition,
    require_ready: bool,
) -> None:
    media_public_ids = references.media_public_ids

    if not media_public_ids:
        return

    if composition is None or not composition.pk:
        raise ValidationError(
            {
                "document": [
                    (
                        "Media layers can only reference "
                        "assets already attached to a composition."
                    ),
                ],
            }
        )

    normalized_ids: set[uuid.UUID] = set()
    invalid_ids: list[str] = []

    for value in media_public_ids:
        try:
            normalized_ids.add(
                uuid.UUID(value)
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ):
            invalid_ids.append(value)

    if invalid_ids:
        raise ValidationError(
            {
                "document": [
                    (
                        "Invalid creative media identifiers: "
                        + ", ".join(
                            sorted(invalid_ids)
                        )
                    ),
                ],
            }
        )

    media_items = list(
        CreativeCompositionMedia.objects
        .select_related(
            "source_content_type"
        )
        .filter(
            composition=composition,
            public_id__in=normalized_ids,
            is_active=True,
        )
    )

    mapping = {
        str(item.public_id): item
        for item in media_items
    }

    missing = sorted(
        str(value)
        for value in normalized_ids
        if str(value) not in mapping
    )

    if missing:
        raise ValidationError(
            {
                "document": [
                    (
                        "Creative media does not belong "
                        "to this composition: "
                        + ", ".join(missing)
                    ),
                ],
            }
        )

    if require_ready:
        unavailable = sorted(
            public_id
            for public_id, item in mapping.items()
            if not item.is_available()
        )

        if unavailable:
            raise ValidationError(
                {
                    "document": [
                        (
                            "Creative media is not ready: "
                            + ", ".join(unavailable)
                        ),
                    ],
                }
            )

    invalid_image_media = sorted(
        media_id
        for media_id
        in references.image_media_public_ids
        if (
            media_id in mapping
            and mapping[media_id].media_type
            != CreativeCompositionMedia.MediaType.IMAGE
        )
    )

    if invalid_image_media:
        raise ValidationError(
            {
                "document": [
                    (
                        "Image layers reference non-image media: "
                        + ", ".join(invalid_image_media)
                    ),
                ],
            }
        )

    invalid_video_media = sorted(
        media_id
        for media_id
        in references.video_media_public_ids
        if (
            media_id in mapping
            and mapping[media_id].media_type
            != CreativeCompositionMedia.MediaType.VIDEO
        )
    )

    if invalid_video_media:
        raise ValidationError(
            {
                "document": [
                    (
                        "Video layers reference non-video media: "
                        + ", ".join(invalid_video_media)
                    ),
                ],
            }
        )