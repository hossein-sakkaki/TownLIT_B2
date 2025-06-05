import os
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files import File
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
        # باز کردن فایل نهایی تبدیل‌شده
        with open(os.path.join(settings.MEDIA_ROOT, relative_path), 'rb') as f:
            django_file = File(f)
            # تولید نام مناسب (مثلاً فقط نام فایل بدون مسیر)
            filename = os.path.basename(relative_path)

            # حذف فایل قبلی اگر وجود دارد
            old_file = getattr(instance, field_name)
            if old_file and old_file.name != relative_path:
                old_file.delete(save=False)

            # ذخیره در فیلد، با استفاده از File object
            getattr(instance, field_name).save(filename, django_file, save=True)

        logger.info(f"✅ Updated file field '{field_name}' to: {relative_path}")

    except Exception as e:
        logger.error(f"❌ Failed to update file field '{field_name}' on {instance}: {e}")
        raise

    
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
        logger.error(f"❌ convert_image_to_jpg_task failed: {e}")


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
        logger.error(f"❌ convert_video_to_mp4_task failed: {e}")



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
        logger.error(f"❌ convert_audio_to_mp3_task failed: {e}")

