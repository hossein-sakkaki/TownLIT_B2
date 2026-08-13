# apps/creative_editor/services/media_loader.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-10.
# Last Update by Hossein Sakkaki on 2026-08-10.
#

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps

from apps.creative_editor.models import (
    CreativeCompositionMedia,
)


class CreativeMediaLoadError(Exception):
    """
    Raised when composition media cannot be loaded.
    """


@dataclass(frozen=True)
class LoadedCreativeMediaImage:
    image: Image.Image


def load_composition_media_image(
    media: CreativeCompositionMedia,
) -> LoadedCreativeMediaImage:
    """
    Load one canonical image source.
    """

    if media.media_type != media.MediaType.IMAGE:
        raise CreativeMediaLoadError(
            "Creative media is not an image."
        )

    if not media.is_available():
        raise CreativeMediaLoadError(
            "Creative media is unavailable."
        )

    if media.source_mode == media.SourceMode.UPLOAD:
        field = media.source_image

    elif media.source_mode == media.SourceMode.CONTENT_REFERENCE:
        target = media.source_content_object

        if target is None:
            raise CreativeMediaLoadError(
                "Creative media source object is unavailable."
            )

        field = getattr(
            target,
            media.source_field_name,
            None,
        )

    else:
        raise CreativeMediaLoadError(
            "Unsupported creative media source mode."
        )

    if not field or not getattr(field, "name", None):
        raise CreativeMediaLoadError(
            "Creative media source file is unavailable."
        )

    try:
        field.open("rb")

        try:
            image = Image.open(field)
            image.load()
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA")

        finally:
            field.close()

    except Exception as exc:
        raise CreativeMediaLoadError(
            "Creative media image could not be loaded."
        ) from exc

    return LoadedCreativeMediaImage(
        image=image
    )