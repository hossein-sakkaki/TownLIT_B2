# apps/media_conversion/tasks.py
import os, time, logging
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import close_old_connections

from utils.common.utils import FileUpload
from utils.common.image_utils import convert_image_to_jpg
from utils.common.video_utils import convert_video_to_multi_hls
from utils.common.audio_utils import convert_audio_to_mp3

logger = logging.getLogger(__name__)


def get_instance(app_label, model_name, pk, retries=3, delay=0.2):
    """
    Fetch model instance with tiny retry window to avoid race with on_commit.
    """
    Model = apps.get_model(app_label=app_label, model_name=model_name)
    for i in range(retries + 1):
        try:
            return Model.objects.get(pk=pk)
        except Model.DoesNotExist:
            if i < retries:
                time.sleep(delay)
                continue
            raise


# --- Optional activation hook --------------------------------------------
def _maybe_activate_after_convert(instance, field_name: str, update_fields: list[str]) -> None:
    """
    Model-level opt-in:
      def on_media_converted(self, field_name, update_fields): ...
    Allows toggling is_active safely and appending 'is_active' to update_fields.
    """
    hook = getattr(instance, "on_media_converted", None)
    if callable(hook):
        try:
            hook(field_name, update_fields)
        except Exception as e:
            logger.warning("Activation hook failed for %s.%s: %s",
                           instance.__class__.__name__, field_name, e)


# --- Bind converted path to FileField (no re-upload) ----------------------
def handle_converted_file_update(model_name: str, app_label: str, instance_id: int,
                                 field_name: str, relative_path: str) -> None:
    """
    Bind already-uploaded converted file (at `relative_path`) to model field.
    IMPORTANT: Do NOT re-upload; just set .name and save(update_fields=...).
    """
    try:
        if os.path.isabs(relative_path):
            raise ValueError("Relative path expected, got absolute path.")

        # use the same retry-aware getter we use elsewhere
        instance = get_instance(app_label, model_name, instance_id)

        if not hasattr(instance, field_name):
            raise AttributeError(f"Field '{field_name}' does not exist on model '{model_name}'")

        # Defensive: ensure uploaded object exists in storage
        if not default_storage.exists(relative_path):
            logger.error("Converted path not found in storage: %s", relative_path)
            return

        # ✅ Just bind the path; DO NOT upload again
        file_field = getattr(instance, field_name)
        file_field.name = relative_path

        update_fields = [field_name]
        if hasattr(instance, "is_converted"):
            instance.is_converted = True
            update_fields.append("is_converted")

        # Optional, model-defined activation (safe & generic)
        _maybe_activate_after_convert(instance, field_name, update_fields)

        instance.save(update_fields=update_fields)
        logger.info("✅ File field '%s' updated on %s[%s] -> %s",
                    field_name, model_name, instance_id, relative_path)

    except Exception as e:
        logger.error("❌ Failed to update file field '%s' on %s[%s]: %s",
                     field_name, model_name, instance_id, e)
        raise



# ------------------ VIDEO -----------------------------------------------
@shared_task(queue="video")
def convert_video_to_multi_hls_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    """
    Convert uploaded video to multi-bitrate HLS and update the model field.
    """
    try:
        close_old_connections()
        logger.info("🚧 Celery Task triggered for video conversion: %s (id=%s)", model_name, instance_id)

        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        # Convert & upload; returns storage-relative master.m3u8
        relative_path = convert_video_to_multi_hls(source_path, instance, upload)

        # Unified update (no re-upload)
        handle_converted_file_update(model_name, app_label, instance_id, field_name, relative_path)
        logger.info("✅ HLS conversion complete: %s", relative_path)

        # Optional: cleanup original
        if source_path and default_storage.exists(source_path):
            default_storage.delete(source_path)
            logger.info("🗑️ Deleted original uploaded file: %s", source_path)

    except Exception as e:
        logger.error("❌ convert_video_to_multi_hls_task failed for %s (id=%s) – error: %s",
                     model_name, instance_id, e)
        raise
        
        

# @shared_task(queue="video")
# def convert_video_to_multi_hls_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
#     try:
#         close_old_connections()
#         logger.info(f"🚧 Celery Task triggered for video conversion: {model_name} (id={instance_id})")

#         instance = get_instance(app_label, model_name, instance_id, retries=3, delay=0.2)
#         upload = FileUpload(**fileupload)

#         relative_path = convert_video_to_multi_hls(source_path, instance, upload)
#         setattr(instance, field_name, relative_path)

#         update_fields = [field_name]
#         if hasattr(instance, "is_converted"):
#             instance.is_converted = True
#             update_fields.append("is_converted")

#         instance.save(update_fields=update_fields)
#         logger.info(f"✅ HLS conversion complete: {relative_path}")

#         if source_path and default_storage.exists(source_path):
#             default_storage.delete(source_path)
#             logger.info(f"🗑️ Deleted original uploaded file: {source_path}")

#     except Exception as e:
#         logger.error(f"❌ convert_video_to_multi_hls_task failed for {model_name} (id={instance_id}) – error: {e}")

    
    
# ------------------ IMAGE -----------------------------------------------
@shared_task(queue="video")
def convert_image_to_jpg_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        close_old_connections()

        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        # Convert & upload; returns storage-relative .jpg
        relative_path = convert_image_to_jpg(source_path, instance, upload)

        # Bind result without re-upload
        handle_converted_file_update(model_name, app_label, instance_id, field_name, relative_path)

        logger.info("✅ Image conversion and model update successful: %s", relative_path)

    except Exception as e:
        logger.error("❌ convert_image_to_jpg_task failed for %s (id=%s) – error: %s",
                     model_name, instance_id, e)
        raise


# ------------------ AUDIO -----------------------------------------------
@shared_task(queue="video")
def convert_audio_to_mp3_task(model_name, app_label, instance_id, field_name, source_path, fileupload):
    try:
        close_old_connections()

        instance = get_instance(app_label, model_name, instance_id)
        upload = FileUpload(**fileupload)

        # Convert & upload; returns storage-relative .mp3
        relative_path = convert_audio_to_mp3(source_path, instance, upload)

        # Bind result without re-upload
        handle_converted_file_update(model_name, app_label, instance_id, field_name, relative_path)

        # Optional: cleanup original
        if source_path and default_storage.exists(source_path):
            default_storage.delete(source_path)
            logger.info("🗑️ Deleted original uploaded audio: %s", source_path)

        logger.info("✅ Audio conversion and model update successful: %s", relative_path)

    except Exception as e:
        logger.error("❌ convert_audio_to_mp3_task failed for %s (id=%s) – error: %s",
                     model_name, instance_id, e)
        raise