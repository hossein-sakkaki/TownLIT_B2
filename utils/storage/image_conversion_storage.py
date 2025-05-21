# utils/common/storage.py

import os
import uuid
import logging
from django.core.files.storage import FileSystemStorage
from utils.common.image_utils import convert_image_to_jpg
from utils.common.utils import FileUpload

logger = logging.getLogger(__name__)

class HEICToJPEGStorage(FileSystemStorage):
    """
    Custom storage backend that converts unsupported image formats
    (HEIC, TIFF, WebP) to JPG using FileUpload path structure.
    """

    SUPPORTED_EXTENSIONS = [".heic", ".heif", ".tiff", ".tif", ".webp"]

    def __init__(self, fileupload: FileUpload, *args, **kwargs):
        """
        Must pass a FileUpload instance to define where converted files go.
        """
        self.fileupload = fileupload
        super().__init__(*args, **kwargs)

    def _save(self, name, content):
        extension = os.path.splitext(name)[1].lower()

        # 🔁 ذخیره اولیه
        saved_name = super()._save(name, content)
        saved_path = self.path(saved_name)

        if extension in self.SUPPORTED_EXTENSIONS:
            try:
                converted_relative_path = convert_image_to_jpg(
                    source_path=saved_path,
                    instance=None,
                    fileupload=self.fileupload
                )

                converted_abs_path = os.path.join(self.location, converted_relative_path)

                if os.path.exists(saved_path) and saved_path != converted_abs_path:
                    os.remove(saved_path)

                logger.info(f"✅ Converted image saved as: {converted_relative_path}")
                return converted_relative_path

            except Exception as e:
                logger.error(f"❌ Image conversion failed during storage: {e}")
                return saved_name

        return saved_name
