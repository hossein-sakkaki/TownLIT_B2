# apps/communication/services/media.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.core.storages import PublicEmailStorage


MAX_EMAIL_IMAGE_BYTES = 30 * 1024 * 1024
MAX_EMAIL_IMAGE_DIMENSION = 30000

ALLOWED_IMAGE_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "GIF": ".gif",
}


class EmailMediaUploadError(ValueError):
    pass


@dataclass(frozen=True)
class UploadedEmailImage:
    key: str
    url: str
    width: int
    height: int
    file_size: int


class EmailMediaUploadService:
    """
    Validate and store permanent public images used inside emails.
    """

    def __init__(self):
        self.storage = PublicEmailStorage()

    def upload_campaign_image(
        self,
        *,
        campaign_id: int,
        uploaded_file: UploadedFile,
    ) -> UploadedEmailImage:
        if not uploaded_file:
            raise EmailMediaUploadError(
                "Please choose an image to upload."
            )

        file_size = uploaded_file.size or 0

        if file_size <= 0:
            raise EmailMediaUploadError(
                "The selected image is empty."
            )

        if file_size > MAX_EMAIL_IMAGE_BYTES:
            raise EmailMediaUploadError(
                "Email images must be 30 MB or smaller."
            )

        image_format, width, height = self._inspect_image(
            uploaded_file
        )

        extension = ALLOWED_IMAGE_FORMATS.get(
            image_format
        )

        if not extension:
            raise EmailMediaUploadError(
                "Use a PNG, JPG or GIF image."
            )

        now = timezone.now()

        relative_key = str(
            PurePosixPath(
                "campaigns",
                str(campaign_id),
                now.strftime("%Y"),
                now.strftime("%m"),
                f"{uuid4().hex}{extension}",
            )
        )

        uploaded_file.seek(0)

        saved_name = self.storage.save(
            relative_key,
            uploaded_file,
        )

        return UploadedEmailImage(
            key=saved_name,
            url=self.storage.url(saved_name),
            width=width,
            height=height,
            file_size=file_size,
        )

    def _inspect_image(
        self,
        uploaded_file: UploadedFile,
    ) -> tuple[str, int, int]:
        try:
            uploaded_file.seek(0)

            with Image.open(uploaded_file) as image:
                image_format = (
                    image.format or ""
                ).upper()

                width, height = image.size

                if (
                    width <= 0
                    or height <= 0
                    or width > MAX_EMAIL_IMAGE_DIMENSION
                    or height > MAX_EMAIL_IMAGE_DIMENSION
                ):
                    raise EmailMediaUploadError(
                        "The image dimensions are not supported."
                    )

                image.verify()

        except EmailMediaUploadError:
            raise

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise EmailMediaUploadError(
                "The selected file is not a valid image."
            ) from exc

        finally:
            uploaded_file.seek(0)

        return image_format, width, height