# utils/mixins/media_conversion.py

import os
import mimetypes
import logging
import hashlib

from django.db import transaction
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.services.jobs import upsert_job, attach_task
from apps.media_conversion.models import MediaJobStatus, MediaConversionJob

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

    # Short English comment: small enqueue delay reduces race with DB commit / replica lag
    MEDIA_ENQUEUE_COUNTDOWN_SECONDS = 2

    # Short English comment: short distributed lock to prevent duplicate enqueue bursts
    MEDIA_ENQUEUE_LOCK_TTL_SECONDS = 300

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

    def _get_content_type(self):
        return ContentType.objects.get_for_model(self, for_concrete_model=False)

    def _make_enqueue_lock_key(self, field_name: str, kind: str, source_path: str) -> str:
        raw = f"{self._meta.label_lower}:{self.pk}:{field_name}:{kind}:{source_path}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"media:enqueue:{digest}"

    def _acquire_enqueue_lock(self, field_name: str, kind: str, source_path: str) -> bool:
        key = self._make_enqueue_lock_key(field_name, kind, source_path)
        ttl = int(getattr(self, "MEDIA_ENQUEUE_LOCK_TTL_SECONDS", 300) or 300)

        try:
            acquired = cache.add(key, "1", timeout=ttl)
            if not acquired:
                logger.info(
                    "⏭️ skip enqueue lock hit: %s[%s] %s (%s)",
                    self.__class__.__name__,
                    getattr(self, "pk", None),
                    field_name,
                    kind,
                )
            return acquired
        except Exception as e:
            # Fail open: conversion must still proceed even if cache backend is unavailable.
            logger.warning(
                "⚠️ enqueue lock unavailable for %s[%s] %s (%s): %s",
                self.__class__.__name__,
                getattr(self, "pk", None),
                field_name,
                kind,
                e,
            )
            return True

    def _get_existing_job_for_source(self, field_name: str, kind: str, source_path: str):
        try:
            ct = self._get_content_type()
            return (
                MediaConversionJob.objects
                .filter(
                    content_type=ct,
                    object_id=self.pk,
                    field_name=field_name,
                    kind=kind,
                    source_path=source_path,
                )
                .order_by("-created_at", "-id")
                .first()
            )
        except Exception as e:
            logger.warning(
                "⚠️ could not inspect existing job for %s[%s] %s (%s): %s",
                self.__class__.__name__,
                getattr(self, "pk", None),
                field_name,
                kind,
                e,
            )
            return None

    def _should_skip_duplicate_enqueue(self, field_name: str, kind: str, source_path: str) -> bool:
        existing_job = self._get_existing_job_for_source(field_name, kind, source_path)
        if not existing_job:
            return False

        # Active duplicate job already exists.
        if existing_job.status in {MediaJobStatus.QUEUED, MediaJobStatus.PROCESSING}:
            logger.info(
                "⏭️ skip duplicate enqueue: active job exists for %s[%s] %s (%s) job_id=%s status=%s",
                self.__class__.__name__,
                getattr(self, "pk", None),
                field_name,
                kind,
                existing_job.id,
                existing_job.status,
            )
            return True

        # Same source already converted successfully.
        if existing_job.status == MediaJobStatus.DONE:
            logger.info(
                "⏭️ skip duplicate enqueue: already DONE for %s[%s] %s (%s) job_id=%s",
                self.__class__.__name__,
                getattr(self, "pk", None),
                field_name,
                kind,
                existing_job.id,
            )
            return True

        # FAILED / CANCELED jobs are allowed to requeue.
        return False

    def _dispatch_conversion_task(self, *, job, task, task_kwargs, queue="video"):
        countdown = int(getattr(self, "MEDIA_ENQUEUE_COUNTDOWN_SECONDS", 2) or 2)

        async_result = task.apply_async(
            kwargs=task_kwargs,
            queue=queue,
            countdown=countdown,
        )

        attach_task(job, async_result.id, queue=queue)
        return async_result

    def _enqueue_conversion_tasks(self):
        """Real enqueuing logic; called only AFTER COMMIT."""
        # Skip entirely if instance is already marked as converted
        if getattr(self, "is_converted", False):
            logger.info(
                "⏭️ skip enqueue: %s[%s] already converted",
                self.__class__.__name__,
                getattr(self, "pk", None),
            )
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
                        self.__class__.__name__,
                        field_name,
                        mime_type,
                    )
                    continue

                # Prevent same-source duplicate enqueue bursts.
                if self._should_skip_duplicate_enqueue(field_name, kind, source_path):
                    continue

                # Add short distributed lock for near-simultaneous save/signal storms.
                if not self._acquire_enqueue_lock(field_name, kind, source_path):
                    continue

                if kind == KIND_IMAGE:
                    if ext in (".jpg", ".jpeg", ".png"):
                        logger.info(
                            "⏭️ skip image: already final (%s) – %s.%s",
                            ext,
                            self.__class__.__name__,
                            field_name,
                        )
                        # Do NOT mark object as converted here.
                        # A final image/thumbnail does not mean video conversion is done.
                        continue

                    job = upsert_job(
                        instance=self,
                        field_name=field_name,
                        kind="image",
                        status=MediaJobStatus.QUEUED,
                        source_path=source_path,
                        message="Queued for image processing",
                    )

                    self._dispatch_conversion_task(
                        job=job,
                        task=convert_image_to_jpg_task,
                        queue="video",
                        task_kwargs={
                            "model_name": self.__class__.__name__,
                            "app_label": self._meta.app_label,
                            "instance_id": self.pk,
                            "field_name": field_name,
                            "source_path": source_path,
                            "fileupload": upload.to_dict(),
                        },
                    )
                    scheduled_any = True

                elif kind == KIND_AUDIO:
                    if ext == ".mp3":
                        job = upsert_job(
                            instance=self,
                            field_name=field_name,
                            kind="audio",
                            status=MediaJobStatus.DONE,
                            source_path=source_path,
                            message="Audio already in final format",
                        )

                        if hasattr(self, "is_converted") and not self.is_converted:
                            self.is_converted = True
                            self.save(update_fields=["is_converted"])

                        scheduled_any = True
                        logger.info(
                            "✅ audio final format (.mp3) – job created as DONE – %s.%s",
                            self.__class__.__name__,
                            field_name,
                        )
                        continue

                    job = upsert_job(
                        instance=self,
                        field_name=field_name,
                        kind="audio",
                        status=MediaJobStatus.QUEUED,
                        source_path=source_path,
                        message="Queued for audio processing",
                    )

                    self._dispatch_conversion_task(
                        job=job,
                        task=convert_audio_to_mp3_task,
                        queue="video",
                        task_kwargs={
                            "model_name": self.__class__.__name__,
                            "app_label": self._meta.app_label,
                            "instance_id": self.pk,
                            "field_name": field_name,
                            "source_path": source_path,
                            "fileupload": upload.to_dict(),
                        },
                    )
                    scheduled_any = True

                elif kind == KIND_VIDEO:
                    # Prevent HLS→HLS loops (master.m3u8/segments)
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

                    self._dispatch_conversion_task(
                        job=job,
                        task=convert_video_to_multi_hls_task,
                        queue="video",
                        task_kwargs={
                            "model_name": self.__class__.__name__,
                            "app_label": self._meta.app_label,
                            "instance_id": self.pk,
                            "field_name": field_name,
                            "source_path": source_path,
                            "fileupload": upload.to_dict(),
                        },
                    )
                    scheduled_any = True

            except Exception as e:
                logger.warning(
                    "❌ Failed to dispatch conversion for %s.%s: %s",
                    self.__class__.__name__,
                    field_name,
                    e,
                )

        if not scheduled_any:
            logger.info(
                "ℹ️ no conversion task scheduled for %s[%s]",
                self.__class__.__name__,
                getattr(self, "pk", None),
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