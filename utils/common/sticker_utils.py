# utils/common/sticker_utils.py

from __future__ import annotations

import os
import tempfile
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from PIL import Image, ImageOps

from utils.common.utils import FileUpload


STICKER_MAX_DIMENSION = 2048


def convert_sticker_to_png(
    source_path: str,
    instance,
    fileupload: FileUpload,
) -> str:
    """
    Convert a static sticker to optimized PNG.
    """

    source_key = str(
        source_path or ""
    ).strip().lstrip("/")

    if not source_key:
        raise ValueError(
            "Sticker source path is empty."
        )

    with default_storage.open(
        source_key,
        "rb",
    ) as source:
        image = Image.open(source)
        image.load()

    image = ImageOps.exif_transpose(
        image
    )

    if image.mode != "RGBA":
        image = image.convert("RGBA")

    image.thumbnail(
        (
            STICKER_MAX_DIMENSION,
            STICKER_MAX_DIMENSION,
        ),
        resample=Image.Resampling.LANCZOS,
    )

    today_path = instance.created_at.strftime(
        "%Y/%m/%d"
    )

    output_key = (
        f"{fileupload.app_name}/"
        f"{fileupload.direction}/"
        f"{fileupload.folder}/"
        f"{today_path}/"
        f"{uuid.uuid4().hex}.png"
    )

    with tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    ) as temporary_file:
        temporary_path = temporary_file.name

    try:
        image.save(
            temporary_path,
            format="PNG",
            optimize=True,
            compress_level=9,
        )

        with open(
            temporary_path,
            "rb",
        ) as output:
            saved_key = default_storage.save(
                output_key,
                ContentFile(
                    output.read()
                ),
            )

        return str(
            saved_key
        ).lstrip("/")

    finally:
        try:
            os.remove(
                temporary_path
            )
        except OSError:
            pass