# apps/creative_editor/services/render_resources.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-07-21.
# Last Update by Hossein Sakkaki on 2026-08-10.
#

from __future__ import annotations

import uuid

from dataclasses import dataclass

from apps.creative_editor.models import (
    CreativeComposition,
    CreativeCompositionMedia,
    StickerAsset,
)


class CreativeResourceError(Exception):
    """
    Raised when render resources are invalid.
    """


@dataclass(frozen=True)
class CreativeRenderResources:
    """
    Resources required by one render.
    """

    stickers: dict[
        str,
        StickerAsset,
    ]

    media: dict[
        str,
        CreativeCompositionMedia,
    ]


def extract_resource_ids(
    document: dict,
) -> tuple[
    set[str],
    set[str],
]:
    """
    Extract sticker and media UUIDs.
    """

    sticker_ids: set[str] = set()
    media_ids: set[str] = set()

    for layer in document.get("layers") or []:
        if not isinstance(layer, dict):
            continue

        layer_type = layer.get("type")
        content = layer.get("content") or {}

        if not isinstance(content, dict):
            continue

        if layer_type == "sticker":
            raw_value = str(
                content.get(
                    "sticker_id",
                    "",
                )
            ).strip()

            if raw_value:
                sticker_ids.add(
                    _canonical_uuid(
                        raw_value,
                        resource_name="sticker",
                    )
                )

        elif layer_type in {
            "image",
            "video",
        }:
            raw_value = str(
                content.get(
                    "media_id",
                    "",
                )
            ).strip()

            if raw_value:
                media_ids.add(
                    _canonical_uuid(
                        raw_value,
                        resource_name="media",
                    )
                )

    return (
        sticker_ids,
        media_ids,
    )


def _canonical_uuid(
    value: str,
    *,
    resource_name: str,
) -> str:
    try:
        return str(
            uuid.UUID(value)
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ) as exc:
        raise CreativeResourceError(
            (
                "Document contains an invalid "
                f"{resource_name} id: {value}"
            )
        ) from exc


def resolve_render_resources(
    *,
    document: dict,
    composition: CreativeComposition,
) -> CreativeRenderResources:
    """
    Resolve database resources once.
    """

    (
        sticker_ids,
        media_ids,
    ) = extract_resource_ids(
        document
    )

    stickers: dict[
        str,
        StickerAsset,
    ] = {}

    if sticker_ids:
        normalized_ids = {
            uuid.UUID(value)
            for value in sticker_ids
        }

        queryset = (
            StickerAsset.objects
            .select_related("pack")
            .filter(
                public_id__in=normalized_ids,
                is_active=True,
                is_converted=True,
                pack__is_active=True,
            )
        )

        stickers = {
            str(item.public_id): item
            for item in queryset
        }

        missing = sorted(
            sticker_ids
            - set(stickers.keys())
        )

        if missing:
            raise CreativeResourceError(
                (
                    "Unavailable sticker resources: "
                    + ", ".join(missing)
                )
            )

    media: dict[
        str,
        CreativeCompositionMedia,
    ] = {}

    if media_ids:
        normalized_ids = {
            uuid.UUID(value)
            for value in media_ids
        }

        queryset = (
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

        media = {
            str(item.public_id): item
            for item in queryset
        }

        missing = sorted(
            media_ids
            - set(media.keys())
        )

        if missing:
            raise CreativeResourceError(
                (
                    "Unavailable composition media: "
                    + ", ".join(missing)
                )
            )

        unavailable = sorted(
            public_id
            for public_id, item in media.items()
            if not item.is_available()
        )

        if unavailable:
            raise CreativeResourceError(
                (
                    "Composition media is not ready: "
                    + ", ".join(unavailable)
                )
            )

    return CreativeRenderResources(
        stickers=stickers,
        media=media,
    )