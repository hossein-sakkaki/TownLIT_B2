# apps/creative_editor/services/render_output.py

from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.core.files import File
from django.core.files.base import (
    ContentFile,
)
from django.core.files.storage import (
    default_storage,
)

from PIL import Image

from apps.creative_editor.constants import (
    CREATIVE_RENDER_OUTPUT_QUALITY,
    CREATIVE_RENDER_THUMBNAIL_MAX_HEIGHT,
    CREATIVE_RENDER_THUMBNAIL_MAX_WIDTH,
    CREATIVE_RENDER_THUMBNAIL_QUALITY,
)


@dataclass(frozen=True)
class CreativeRenderOutput:
    """
    Persisted canonical render files.
    """

    output_path: str
    thumbnail_path: str
    width: int
    height: int

@dataclass(frozen=True)
class CreativeVideoRenderOutput:
    video_path: str
    thumbnail_path: str
    width: int
    height: int
    duration_ms: int
    
        
def build_render_storage_key(
    *,
    composition_id: int,
    revision: int,
    kind: str,
) -> str:
    """
    Build a unique storage destination.
    """

    today = datetime.utcnow().strftime(
        "%Y/%m/%d"
    )

    filename = (
        f"{uuid.uuid4().hex}.jpg"
    )

    return (
        "creative_editor/"
        f"{kind}/compositions/"
        f"{composition_id}/"
        f"revision-{revision}/"
        f"{today}/"
        f"{filename}"
    )


def image_to_jpeg_bytes(
    image: Image.Image,
    *,
    quality: int,
) -> bytes:
    """
    Encode an image as optimized JPEG.
    """

    rgb = image.convert(
        "RGB"
    )

    buffer = io.BytesIO()

    rgb.save(
        buffer,
        format="JPEG",
        quality=int(quality),
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )

    return buffer.getvalue()


def build_thumbnail(
    image: Image.Image,
) -> Image.Image:
    """
    Build a bounded composition thumbnail.
    """

    thumbnail = image.copy()

    thumbnail.thumbnail(
        (
            CREATIVE_RENDER_THUMBNAIL_MAX_WIDTH,
            CREATIVE_RENDER_THUMBNAIL_MAX_HEIGHT,
        ),
        resample=Image.Resampling.LANCZOS,
    )

    return thumbnail


def persist_render_output(
    *,
    image: Image.Image,
    composition_id: int,
    revision: int,
) -> CreativeRenderOutput:
    """
    Save canonical image and thumbnail.
    """

    output_key = build_render_storage_key(
        composition_id=composition_id,
        revision=revision,
        kind="renders",
    )

    thumbnail_key = build_render_storage_key(
        composition_id=composition_id,
        revision=revision,
        kind="thumbnails",
    )

    output_bytes = image_to_jpeg_bytes(
        image,
        quality=CREATIVE_RENDER_OUTPUT_QUALITY,
    )

    thumbnail = build_thumbnail(
        image
    )

    thumbnail_bytes = image_to_jpeg_bytes(
        thumbnail,
        quality=(
            CREATIVE_RENDER_THUMBNAIL_QUALITY
        ),
    )

    saved_output_key = (
        default_storage.save(
            output_key,
            ContentFile(output_bytes),
        )
    )

    try:
        saved_thumbnail_key = (
            default_storage.save(
                thumbnail_key,
                ContentFile(
                    thumbnail_bytes
                ),
            )
        )

    except Exception:
        try:
            if default_storage.exists(
                saved_output_key
            ):
                default_storage.delete(
                    saved_output_key
                )
        except Exception:
            pass

        raise

    return CreativeRenderOutput(
        output_path=str(
            saved_output_key
        ).lstrip("/"),
        thumbnail_path=str(
            saved_thumbnail_key
        ).lstrip("/"),
        width=int(image.width),
        height=int(image.height),
    )


def delete_render_output(
    output: CreativeRenderOutput,
) -> None:
    """
    Best-effort cleanup for stale output.
    """

    for key in (
        output.output_path,
        output.thumbnail_path,
    ):
        try:
            normalized = str(
                key or ""
            ).lstrip("/")

            if (
                normalized
                and default_storage.exists(
                    normalized
                )
            ):
                default_storage.delete(
                    normalized
                )

        except Exception:
            pass
        

def build_video_render_storage_key(
    *,
    composition_id: int,
    revision: int,
) -> str:
    today = datetime.utcnow().strftime(
        "%Y/%m/%d"
    )

    return (
        "creative_editor/"
        "renders/compositions/"
        f"{composition_id}/"
        f"revision-{revision}/"
        f"{today}/"
        f"{uuid.uuid4().hex}.mp4"
    )
    
def persist_video_render_output(
    *,
    local_video_path: str,
    poster: Image.Image,
    composition_id: int,
    revision: int,
    width: int,
    height: int,
    duration_ms: int,
) -> CreativeVideoRenderOutput:
    video_key = build_video_render_storage_key(
        composition_id=composition_id,
        revision=revision,
    )

    thumbnail_key = build_render_storage_key(
        composition_id=composition_id,
        revision=revision,
        kind="thumbnails",
    )

    thumbnail = build_thumbnail(
        poster
    )

    thumbnail_bytes = image_to_jpeg_bytes(
        thumbnail,
        quality=CREATIVE_RENDER_THUMBNAIL_QUALITY,
    )

    with open(
        local_video_path,
        "rb",
    ) as source:
        saved_video_key = default_storage.save(
            video_key,
            File(source),
        )

    try:
        saved_thumbnail_key = default_storage.save(
            thumbnail_key,
            ContentFile(
                thumbnail_bytes
            ),
        )

    except Exception:
        try:
            if default_storage.exists(
                saved_video_key
            ):
                default_storage.delete(
                    saved_video_key
                )
        except Exception:
            pass

        raise

    return CreativeVideoRenderOutput(
        video_path=str(
            saved_video_key
        ).lstrip("/"),
        thumbnail_path=str(
            saved_thumbnail_key
        ).lstrip("/"),
        width=int(width),
        height=int(height),
        duration_ms=int(duration_ms),
    )
    
def delete_video_render_output(
    output: CreativeVideoRenderOutput,
) -> None:
    for key in (
        output.video_path,
        output.thumbnail_path,
    ):
        try:
            normalized = str(
                key or ""
            ).lstrip("/")

            if (
                normalized
                and default_storage.exists(
                    normalized
                )
            ):
                default_storage.delete(
                    normalized
                )

        except Exception:
            pass
        