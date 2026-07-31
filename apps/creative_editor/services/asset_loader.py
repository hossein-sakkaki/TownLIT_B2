# apps/creative_editor/services/asset_loader.py

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from django.core.files.storage import (
    default_storage,
)

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)

from apps.asset_delivery.services.job_resolver import (
    get_latest_done_output_path,
)
from apps.asset_delivery.services.playback_resolver import (
    resolve_fallback_filefield_key,
)
from apps.creative_editor.models import (
    CreativeComposition,
    StickerAsset,
)

logger = logging.getLogger(__name__)


class CreativeAssetError(Exception):
    """
    Raised when a required render asset cannot be loaded.
    """


@dataclass(frozen=True)
class LoadedImageAsset:
    """
    One decoded storage-backed image.
    """

    image: Image.Image
    storage_key: str


def normalize_storage_key(
    value,
) -> str:
    """
    Normalize one storage key.
    """

    return str(
        value or ""
    ).strip().lstrip("/")


def resolve_target_image_key(
    *,
    target,
    field_name: str,
) -> str | None:
    """
    Resolve the latest usable image key.
    """

    job_key = get_latest_done_output_path(
        target_obj=target,
        field_name=field_name,
        kind="image",
    )

    if job_key:
        return normalize_storage_key(
            job_key
        )

    fallback_key = (
        resolve_fallback_filefield_key(
            target,
            field_name,
        )
    )

    if fallback_key:
        return normalize_storage_key(
            fallback_key
        )

    return None


def load_image_from_storage(
    storage_key: str,
) -> LoadedImageAsset:
    """
    Read and decode one image from storage.
    """

    key = normalize_storage_key(
        storage_key
    )

    if not key:
        raise CreativeAssetError(
            "Image storage key is empty."
        )

    try:
        if not default_storage.exists(key):
            raise CreativeAssetError(
                f"Image asset does not exist: {key}"
            )

        with default_storage.open(
            key,
            "rb",
        ) as source:
            payload = source.read()

        if not payload:
            raise CreativeAssetError(
                f"Image asset is empty: {key}"
            )

        image = Image.open(
            io.BytesIO(payload)
        )

        image.load()

        image = ImageOps.exif_transpose(
            image
        )

        if image.mode != "RGBA":
            image = image.convert(
                "RGBA"
            )

        return LoadedImageAsset(
            image=image,
            storage_key=key,
        )

    except CreativeAssetError:
        raise

    except UnidentifiedImageError as exc:
        raise CreativeAssetError(
            f"Invalid image asset: {key}"
        ) from exc

    except Exception as exc:
        logger.exception(
            "creative_editor.asset_load.failed",
            extra={
                "storage_key": key,
            },
        )

        raise CreativeAssetError(
            f"Could not load image asset: {key}"
        ) from exc


def load_composition_source(
    composition: CreativeComposition,
) -> LoadedImageAsset | None:
    """
    Resolve the composition background source.
    """

    if (
        composition.source_mode
        == CreativeComposition.SourceMode
        .GENERATED_BACKGROUND
    ):
        return None

    if (
        composition.source_mode
        == CreativeComposition.SourceMode.UPLOAD
    ):
        key = resolve_target_image_key(
            target=composition,
            field_name="source_image",
        )

        if not key:
            raise CreativeAssetError(
                "Composition source image is unavailable."
            )

        return load_image_from_storage(
            key
        )

    if (
        composition.source_mode
        == CreativeComposition.SourceMode
        .CONTENT_REFERENCE
    ):
        target = (
            composition.source_content_object
        )

        if target is None:
            raise CreativeAssetError(
                "Composition source target no longer exists."
            )

        field_name = (
            composition.source_field_name
            or ""
        ).strip()

        if not field_name:
            raise CreativeAssetError(
                "Composition source field is missing."
            )

        key = resolve_target_image_key(
            target=target,
            field_name=field_name,
        )

        if not key:
            raise CreativeAssetError(
                "Referenced source image is unavailable."
            )

        return load_image_from_storage(
            key
        )

    raise CreativeAssetError(
        "Unsupported composition source mode."
    )


def load_sticker_asset(
    sticker: StickerAsset,
) -> LoadedImageAsset:
    """
    Load one active converted sticker.
    """

    if not sticker.is_available():
        raise CreativeAssetError(
            "Sticker is unavailable."
        )

    key = resolve_target_image_key(
        target=sticker,
        field_name="image",
    )

    if not key:
        raise CreativeAssetError(
            "Sticker image is unavailable."
        )

    return load_image_from_storage(
        key
    )