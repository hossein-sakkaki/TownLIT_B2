import os
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from storages.backends.s3boto3 import S3Boto3Storage
from utils.common.utils import FileUpload
from utils.common.image_utils import convert_image_to_jpg
from utils.common.video_utils import convert_video_to_mp4
from utils.common.audio_utils import convert_audio_to_mp3
import logging

logger = logging.getLogger(__name__)



def get_instance(app_label, model_name, pk):
    model = apps.get_model(app_label=app_label, model_name=model_name)
    return model.objects.get(pk=pk)


# Common Handler Converted -----------------------------------------------------------------------
def handle_converted_file_update(instance, field_name, relative_path):
    try:
        # ✅ جلوگیری از ست کردن مسیر absolute
        if os.path.isabs(relative_path):
            if not isinstance(default_storage, S3Boto3Storage):
                relative_path = os.path.relpath(relative_path, settings.MEDIA_ROOT)
                if not relative_path:
                    raise ValueError(f"Empty relative path passed for field '{field_name}'")

            else:
                raise ValueError("Absolute path provided to S3 storage, which is not allowed.")

        old_file = getattr(instance, field_name)
        if old_file and old_file.name != relative_path:
            old_file.delete(save=False)

        setattr(instance, field_name, relative_path)
        logger.info(f"✅ Updated field '{field_name}' to: {relative_path}")
        logger.debug(f"📁 Final path set on model: {getattr(instance, field_name).name}")
        logger.debug(f"📦 Storage backend: {default_storage.__class__.__name__}")

    except Exception as e:
        logger.error(f"❌ Failed to update file field '{field_name}' on {instance}: {e}")
        raise
    
# Video Convertor Task --------------------------------------------------------------------------
@shared_task
def convert_video_to_mp4_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        relative_path = convert_video_to_mp4(source_path, instance, upload)
        handle_converted_file_update(instance, field_name, relative_path)

        update_fields = [field_name]
        if hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        instance.save(update_fields=update_fields)

        logger.info(f"✅ Video conversion and model update successful: {relative_path}")

    except Exception as e:
        logger.error(f"❌ convert_video_to_mp4_task failed for {model_name} (id={instance_id}) – error: {e}")


    
# Image Convertor Task --------------------------------------------------------------------------
@shared_task
def convert_image_to_jpg_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        relative_path = convert_image_to_jpg(source_path, instance, upload)
        handle_converted_file_update(instance, field_name, relative_path)
        update_fields = [field_name]
        if hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        instance.save(update_fields=update_fields)

        logger.info(f"✅ Image conversion and model update successful: {relative_path}")

    except Exception as e:
        logger.error(f"❌ convert_image_to_jpg_task failed for {model_name} (id={instance_id}) – error: {e}")



# Audio Convertor Task --------------------------------------------------------------------------
@shared_task
def convert_audio_to_mp3_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        relative_path = convert_audio_to_mp3(source_path, instance, upload)
        handle_converted_file_update(instance, field_name, relative_path)

        update_fields = [field_name]
        if hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        instance.save(update_fields=update_fields)

        logger.info(f"✅ Audio conversion and model update successful: {relative_path}")

    except Exception as e:
        logger.error(f"❌ convert_audio_to_mp3_task failed for {model_name} (id={instance_id}) – error: {e}")


