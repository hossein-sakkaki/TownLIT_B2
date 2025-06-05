# utils/mixins/media_conversion.py

import os
import mimetypes
import logging
from validators.mime_type_validator import validate_file_type
from apps.media_conversion.tasks import (
    convert_image_to_jpg_task,
    convert_video_to_mp4_task,
    convert_audio_to_mp3_task,
)

logger = logging.getLogger(__name__)


class MediaConversionMixin:    
    media_conversion_config = {}
    def convert_uploaded_media_async(self):
        
        if getattr(self, "is_converted", False):
            return 
    
        for field_name, fileupload in self.media_conversion_config.items():
            file_field = getattr(self, field_name)

            if not file_field:
                continue

            try:
                source_path = file_field.name

                ext = os.path.splitext(source_path)[1].lower()
                mime_type, _ = mimetypes.guess_type(file_field.name)
                file_type = validate_file_type(file_field.name, mime_type)

                if file_type == "image" and ext not in [".jpg", ".jpeg", ".png"]:
                    convert_image_to_jpg_task.delay(
                        model_name=self.__class__.__name__,
                        app_label=self._meta.app_label,
                        instance_id=self.pk,
                        field_name=field_name,
                        source_path=source_path,
                        fileupload=fileupload.to_dict(),
                    )

                elif file_type == "video" and ext != ".mp4":
                    convert_video_to_mp4_task.delay(
                        model_name=self.__class__.__name__,
                        app_label=self._meta.app_label,
                        instance_id=self.pk,
                        field_name=field_name,
                        source_path=source_path,
                        fileupload=fileupload.to_dict(),
                    )

                elif file_type == "audio" and ext != ".mp3":
                    convert_audio_to_mp3_task.delay(
                        model_name=self.__class__.__name__,
                        app_label=self._meta.app_label,
                        instance_id=self.pk,
                        field_name=field_name,
                        source_path=source_path,
                        fileupload=fileupload.to_dict(),
                    )

            except Exception as e:
                logger.warning(f"❌ Failed to dispatch conversion task for {field_name}: {e}")
