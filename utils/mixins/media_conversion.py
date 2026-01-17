# utils/mixins/media_conversion.py
import os
import mimetypes
import logging
from django.db import transaction

from apps.media_conversion.services.jobs import upsert_job, attach_task
from apps.media_conversion.models import MediaJobStatus

from apps.media_conversion.tasks.video import convert_video_to_multi_hls_task
from apps.media_conversion.tasks.audio import convert_audio_to_mp3_task
from apps.media_conversion.tasks.image import convert_image_to_jpg_task

logger = logging.getLogger(__name__)

KIND_IMAGE = "image"
KIND_VIDEO = "video"
KIND_AUDIO = "audio"


class MediaConversionMixin:
    """
    media_conversion_config can be either:
      {
        "thumbnail": FileUpload(...),   # legacy (kind inferred via mime)
        "avatar":    {"upload": FileUpload(...), "kind": "image"},  # explicit
        "audio":     {"upload": FileUpload(...), "kind": "audio"},
        "video":     {"upload": FileUpload(...), "kind": "video"},
      }
    """
    media_conversion_config = {}

    def _resolve_upload_and_kind(self, cfg, field_name):
        # explicit dict form
        if isinstance(cfg, dict):
            upload = cfg.get("upload") or cfg.get("fileupload")
            kind = cfg.get("kind")
            if upload is None:
                raise ValueError(f"Missing 'upload' for field '{field_name}' in media_conversion_config")
            if kind is not None and kind not in {KIND_IMAGE, KIND_VIDEO, KIND_AUDIO}:
                raise ValueError(f"Invalid 'kind' for field '{field_name}': {kind}")
            return upload, kind

        # legacy FileUpload instance (duck-typing)
        if hasattr(cfg, "to_dict"):
            return cfg, None

        raise ValueError(f"Invalid media_conversion_config entry for field '{field_name}'")

    def _enqueue_conversion_tasks(self):
        """Real enqueuing logic; called only AFTER COMMIT."""
        # ⛔ Skip entirely if instance is already marked as converted
        if getattr(self, "is_converted", False):
            logger.info("⏭️ skip enqueue: %s[%s] already converted", self.__class__.__name__, getattr(self, "pk", None))
            return

        scheduled_any = False

        for field_name, cfg in self.media_conversion_config.items():
            file_field = getattr(self, field_name, None)
            if not file_field:
                continue

            try:
                upload, explicit_kind = self._resolve_upload_and_kind(cfg, field_name)
                source_path = getattr(file_field, "name", None)
                if not source_path:
                    continue

                ext = os.path.splitext(source_path)[1].lower()
                mime_type, _ = mimetypes.guess_type(source_path)

                # decide kind (explicit > by field name > mime)
                kind = explicit_kind
                if kind is None:
                    n = field_name.lower()
                    if n in ("audio", "voice", "sound"):
                        kind = KIND_AUDIO
                    elif n in ("video", "movie", "clip"):
                        kind = KIND_VIDEO
                    elif n in ("thumbnail", "thumb", "image", "photo", "avatar", "banner"):
                        kind = KIND_IMAGE
                if kind is None and mime_type:
                    if mime_type.startswith("image/"):
                        kind = KIND_IMAGE
                    elif mime_type.startswith("audio/"):
                        kind = KIND_AUDIO
                    elif mime_type.startswith("video/"):
                        kind = KIND_VIDEO

                if kind is None:
                    logger.warning(
                        "❓ Unable to infer kind for %s.%s (mime=%s). Skipping.",
                        self.__class__.__name__, field_name, mime_type
                    )
                    continue

                if kind == KIND_IMAGE:
                    if ext in (".jpg", ".jpeg", ".png"):
                        logger.info(
                            "⏭️ skip image: already final (%s) – %s.%s",
                            ext, self.__class__.__name__, field_name
                        )

                        # ✅ CRITICAL FIX:
                        # Image is final → mark converted immediately
                        if hasattr(self, "is_converted") and not self.is_converted:
                            self.is_converted = True
                            self.save(update_fields=["is_converted"])

                        continue

                    job = upsert_job(
                        instance=self,
                        field_name=field_name,
                        kind="image",
                        status=MediaJobStatus.QUEUED,
                        source_path=source_path,
                        message="Queued for image processing",
                    )

                    async_result = convert_image_to_jpg_task.delay(
                        model_name=self.__class__.__name__,
                        app_label=self._meta.app_label,
                        instance_id=self.pk,
                        field_name=field_name,
                        source_path=source_path,
                        fileupload=upload.to_dict(),
                    )

                    attach_task(job, async_result.id, queue="video")
                    scheduled_any = True



                elif kind == KIND_AUDIO:
                    # ✅ already final format → skip
                    if ext == ".mp3":
                        if hasattr(self, "is_converted") and not self.is_converted:
                            self.is_converted = True
                            self.save(update_fields=["is_converted"])

                        logger.info("⏭️ skip audio: already final (.mp3) – %s.%s", self.__class__.__name__, field_name)
                        continue

                    job = upsert_job(
                        instance=self,
                        field_name=field_name,
                        kind="audio",
                        status=MediaJobStatus.QUEUED,
                        source_path=source_path,
                        message="Queued for audio processing",
                    )

                    async_result = convert_audio_to_mp3_task.delay(
                        model_name=self.__class__.__name__,
                        app_label=self._meta.app_label,
                        instance_id=self.pk,
                        field_name=field_name,
                        source_path=source_path,
                        fileupload=upload.to_dict(),
                    )

                    attach_task(job, async_result.id, queue="video")
                    scheduled_any = True

                elif kind == KIND_VIDEO:
                    # ⛔ prevent HLS→HLS loops (master.m3u8/segments)
                    is_hls_artifact = (
                        ext in (".m3u8", ".ts")
                        or source_path.endswith("master.m3u8")
                        or (mime_type in ("application/vnd.apple.mpegurl", "application/x-mpegURL"))
                    )
                    if is_hls_artifact:
                        logger.info("⏭️ skip video: HLS artifact detected (path=%s)", source_path)
                        continue

                    job = upsert_job(
                        instance=self,
                        field_name=field_name,
                        kind="video",
                        status=MediaJobStatus.QUEUED,
                        source_path=source_path,
                        message="Queued for video processing",
                    )

                    async_result = convert_video_to_multi_hls_task.delay(
                        model_name=self.__class__.__name__,
                        app_label=self._meta.app_label,
                        instance_id=self.pk,
                        field_name=field_name,
                        source_path=source_path,
                        fileupload=upload.to_dict(),
                    )

                    attach_task(job, async_result.id, queue="video")
                    scheduled_any = True

            except Exception as e:
                logger.warning(
                    "❌ Failed to dispatch conversion for %s.%s: %s",
                    self.__class__.__name__, field_name, e
                )


    def convert_uploaded_media_async(self):
        """Public API — always defer to AFTER COMMIT."""
        # If already converted, don't even register on_commit
        if getattr(self, "is_converted", False):
            return

        def _after_commit():
            self._enqueue_conversion_tasks()

        # Even if called outside atomic, on_commit still calls immediately.
        transaction.on_commit(_after_commit)
