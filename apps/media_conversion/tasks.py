import os
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
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
def handle_converted_file_update(model_name: str, app_label: str, instance_id: int, field_name: str, relative_path: str):
    try:
        model_class = apps.get_model(app_label=app_label, model_name=model_name)
        instance = model_class.objects.get(pk=instance_id)

        if not hasattr(instance, field_name):
            raise AttributeError(f"Field '{field_name}' does not exist on model '{model_name}'")

        # مسیر کامل فیزیکی فایل برای سیستم‌های local
        abs_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        if not os.path.exists(abs_path):
            logger.error(f"❌ Converted file does not exist at path: {abs_path}")
            return

        # ذخیره فایل در فیلد مدل به صورت Django File
        with default_storage.open(relative_path, 'rb') as f:
            file_field = getattr(instance, field_name)
            file_field.save(
                name=relative_path,  # مسیر نسبی کامل (نه فقط basename)
                content=f,
                save=False
            )

        instance.is_converted = True
        instance.save(update_fields=[field_name, "is_converted"])

        logger.info(f"✅ File field '{field_name}' updated successfully on {instance}")

        # اگر فایل در default_storage وجود ندارد، آن را ذخیره کن (مخصوص لوکال)
        if not default_storage.exists(relative_path):
            with open(abs_path, "rb") as f:
                default_storage.save(relative_path, File(f))

        # فایل فیزیکی را پاک کن اگر روی local بودیم (S3 مسیر temp دارد و این فایل نباید حذف شود)
        if not isinstance(default_storage, type(settings.DEFAULT_FILE_STORAGE)):
            os.remove(abs_path)

    except Exception as e:
        logger.error(f"❌ Failed to update file field '{field_name}' on {model_name}[{instance_id}]: {e}")
        raise
    
# Video Convertor Task --------------------------------------------------------------------------
@shared_task
def convert_video_to_mp4_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        relative_path = convert_video_to_mp4(source_path, instance, upload)
        handle_converted_file_update(model_name, app_label, instance_id, field_name, relative_path)


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


