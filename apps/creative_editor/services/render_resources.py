# apps/creative_editor/services/render_resources.py

from __future__ import annotations

import uuid

from dataclasses import dataclass

from apps.creative_editor.models import (
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


def extract_sticker_ids(
    document: dict,
) -> set[str]:
    """
    Extract canonical sticker UUIDs.
    """

    values: set[str] = set()

    for layer in (
        document.get(
            "layers"
        )
        or []
    ):
        if not isinstance(
            layer,
            dict,
        ):
            continue

        if (
            layer.get("type")
            != "sticker"
        ):
            continue

        content = (
            layer.get(
                "content"
            )
            or {}
        )

        raw_value = str(
            content.get(
                "sticker_id",
                "",
            )
        ).strip()

        if not raw_value:
            continue

        try:
            normalized_value = str(
                uuid.UUID(
                    raw_value
                )
            )
        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise CreativeResourceError(
                (
                    "Document contains an invalid "
                    f"sticker id: {raw_value}"
                )
            ) from exc

        values.add(
            normalized_value
        )

    return values


def resolve_render_resources(
    document: dict,
) -> CreativeRenderResources:
    """
    Resolve all database resources once.
    """

    raw_ids = extract_sticker_ids(
        document
    )

    if not raw_ids:
        return CreativeRenderResources(
            stickers={},
        )

    normalized_ids = {
        uuid.UUID(value)
        for value in raw_ids
    }

    stickers = (
        StickerAsset.objects
        .select_related(
            "pack"
        )
        .filter(
            public_id__in=normalized_ids,
            is_active=True,
            is_converted=True,
            pack__is_active=True,
        )
    )

    mapping = {
        str(sticker.public_id):
            sticker
        for sticker in stickers
    }

    missing = sorted(
        raw_ids
        - set(
            mapping.keys()
        )
    )

    if missing:
        raise CreativeResourceError(
            (
                "Unavailable sticker resources: "
                + ", ".join(
                    missing
                )
            )
        )

    return CreativeRenderResources(
        stickers=mapping,
    )