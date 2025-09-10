# apps/media_conversion/tasks.py
import os
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage 
from django.core.files import File
from django.db import close_old_connections

from utils.common.utils import FileUpload
from utils.common.image_utils import convert_image_to_jpg
from utils.common.video_utils import convert_video_to_multi_hls
from utils.common.audio_utils import convert_audio_to_mp3
import logging

logger = logging.getLogger(__name__)



def get_instance(app_label, model_name, pk):
    model = apps.get_model(app_label=app_label, model_name=model_name)
    return model.objects.get(pk=pk)


# Common Handler Converted -----------------------------------------------------------------------
def handle_converted_file_update(model_name: str, app_label: str, instance_id: int, field_name: str, relative_path: str):
    try:
        if os.path.isabs(relative_path):
            raise ValueError("Relative path expected, got absolute path.")

        model_class = apps.get_model(app_label=app_label, model_name=model_name)
        instance = model_class.objects.get(pk=instance_id)

        if not hasattr(instance, field_name):
            raise AttributeError(f"Field '{field_name}' does not exist on model '{model_name}'")

        # باز کردن فایل نهایی
        with default_storage.open(relative_path, 'rb') as f:
            django_file = File(f)
            file_field = getattr(instance, field_name)

            file_field.save(
                name=os.path.basename(relative_path),
                content=django_file,
                save=False
            )

        if hasattr(instance, "is_converted"):
            instance.is_converted = True

        instance.save(update_fields=[field_name, "is_converted"] if hasattr(instance, "is_converted") else [field_name])
        logger.info(f"✅ File field '{field_name}' updated successfully on {instance}")

        # حذف فایل محلی اگر در لوکال بودیم
        if settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage':
            abs_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)

    except Exception as e:
        logger.error(f"❌ Failed to update file field '{field_name}' on {model_name}[{instance_id}]: {e}")
        raise
    

# Video Convertor Task to HLS --------------------------------------------------------------------------
@shared_task(queue="video")
def convert_video_to_multi_hls_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        close_old_connections()

        logger.info(f"🚧 Celery Task triggered for video conversion: {model_name} (id={instance_id})")

        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        # 🚀 تبدیل فایل ویدیویی به HLS multi-bitrate
        relative_path = convert_video_to_multi_hls(source_path, instance, upload)

        # 🔁 به‌روزرسانی مسیر فایل در مدل (فقط فایل master.m3u8)
        setattr(instance, field_name, relative_path)
        logger.warning(f"🎯 After update: {getattr(instance, field_name, None)}")

        update_fields = [field_name]

        # ✳️ اگر فیلد is_converted وجود دارد، مقداردهی کن
        if hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        instance.save(update_fields=update_fields)
        logger.warning(f"📦 Saved fields: {update_fields}")
        logger.info(f"✅ HLS conversion complete: {relative_path}")

        # 🧹 حذف فایل اصلی آپلودشده پس از موفقیت تبدیل
        if source_path and default_storage.exists(source_path):
            default_storage.delete(source_path)
            logger.info(f"🗑️ Deleted original uploaded file: {source_path}")

    except Exception as e:
        logger.error(
            f"❌ convert_video_to_multi_hls_task failed for {model_name} (id={instance_id}) – error: {e}"
        )

    
    
# Image Convertor Task --------------------------------------------------------------------------
@shared_task
def convert_image_to_jpg_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        relative_path = convert_image_to_jpg(source_path, instance, upload)
        handle_converted_file_update(model_name, app_label, instance_id, field_name, relative_path)

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
        handle_converted_file_update(model_name, app_label, instance_id, field_name, relative_path)


        update_fields = [field_name]
        if hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        instance.save(update_fields=update_fields)

        logger.info(f"✅ Audio conversion and model update successful: {relative_path}")

    except Exception as e:
        logger.error(f"❌ convert_audio_to_mp3_task failed for {model_name} (id={instance_id}) – error: {e}")

