# utils/mixins/media_conversion.py

import os
import mimetypes
import logging
import hashlib
import uuid

from django.db import transaction
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType

from apps.media_conversion.services.jobs import upsert_job, attach_task
from apps.media_conversion.models import MediaJobStatus, MediaConversionJob

from apps.media_conversion.tasks.video import convert_video_to_multi_hls_task
from apps.media_conversion.tasks.audio import convert_audio_to_mp3_task
from apps.media_conversion.tasks.image import convert_image_to_jpg_task
from apps.media_conversion.services.availability import (
    maybe_mark_media_target_available_by_id,
)

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

    def media_conversion_availability_fields(
        self,
    ) -> list[str]:
        """
        Return currently populated media fields that are required before the
        whole target may become available.

        Config contract:

        {
            "video": {
                "upload": VIDEO,
                "kind": "video",
                "required_for_availability": True,
            },
            "thumbnail": {
                "upload": IMAGE,
                "kind": "image",
                "required_for_availability": False,
            },
        }

        Backward compatibility:
        - entries without required_for_availability default to True
        - empty fields are ignored
        """

        required_fields: list[str] = []

        config = getattr(
            self,
            "media_conversion_config",
            None,
        ) or {}

        for field_name, field_config in config.items():
            required = True

            if isinstance(
                field_config,
                dict,
            ):
                required = bool(
                    field_config.get(
                        "required_for_availability",
                        True,
                    )
                )

            if not required:
                continue

            value = getattr(
                self,
                field_name,
                None,
            )

            current_path = str(
                getattr(
                    value,
                    "name",
                    "",
                )
                or ""
            ).strip().lstrip(
                "/"
            )

            if not current_path:
                continue

            required_fields.append(
                field_name
            )

        return required_fields


    def _media_conversion_done_job_matches_current_field(
        self,
        *,
        field_name: str,
    ) -> bool:
        """
        Return True only when the current field generation has a successful
        MediaConversionJob.

        A DONE job is authoritative when either:
        - its output_path equals the model's current bound field, or
        - it has no output_path and its source_path equals the current field.

        The second case supports media already in canonical format, such as an
        uploaded MP3 that does not need transcoding.
        """

        value = getattr(
            self,
            field_name,
            None,
        )

        current_path = str(
            getattr(
                value,
                "name",
                "",
            )
            or ""
        ).strip().lstrip(
            "/"
        )

        if not current_path:
            return False

        content_type = self._get_content_type()

        jobs = (
            MediaConversionJob.objects
            .filter(
                content_type=content_type,
                object_id=self.pk,
                field_name=field_name,
                status=MediaJobStatus.DONE,
            )
            .order_by(
                "-updated_at",
                "-id",
            )
        )

        for job in jobs:
            source_path = str(
                job.source_path
                or ""
            ).strip().lstrip(
                "/"
            )

            output_path = str(
                job.output_path
                or ""
            ).strip().lstrip(
                "/"
            )

            # Normal conversion:
            # raw source -> converted output -> model field points to output.
            if output_path:
                if output_path == current_path:
                    return True

                continue

            # Already-canonical media:
            # no generated output exists, so the successful job references
            # the current source directly.
            if source_path == current_path:
                return True

        return False


    def media_conversion_target_ready_for_availability(
        self,
    ) -> bool:
        """
        Return True only when every currently populated availability-critical
        media field has completed conversion for its current generation.

        A configured field with no current file is ignored.

        Returning False when no required fields are present is intentional:
        custom pipelines such as Moment image_items own their own completion
        lifecycle and must not be finalized by an unrelated generic job.
        """

        if not getattr(
            self,
            "pk",
            None,
        ):
            return False

        required_fields = (
            self.media_conversion_availability_fields()
        )

        if not required_fields:
            return False

        for field_name in required_fields:
            if not (
                self._media_conversion_done_job_matches_current_field(
                    field_name=field_name
                )
            ):
                return False

        return True

    def media_conversion_enqueue_allowed(
        self,
        *,
        field_name: str,
        kind: str,
        source_path: str,
    ) -> bool:
        """
        Optional per-field pre-enqueue gate.

        Models or mixins may override this hook to prevent a specific raw
        media generation from entering Media Conversion.

        Default behavior remains unchanged.
        """

        return True

    def _make_enqueue_lock_key(self, field_name: str, kind: str, source_path: str) -> str:
        raw = f"{self._meta.label_lower}:{self.pk}:{field_name}:{kind}:{source_path}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"media:enqueue:{digest}"

    def _acquire_enqueue_lock(
        self,
        field_name: str,
        kind: str,
        source_path: str,
    ) -> tuple[str, str] | None:
        """
        Acquire a short-lived enqueue lease.

        Returns:
        - (cache_key, ownership_token) when acquired
        - None when another enqueue owns the lease
        - ("", "") when cache is unavailable and enqueue should fail open
        """

        key = self._make_enqueue_lock_key(
            field_name,
            kind,
            source_path,
        )

        token = uuid.uuid4().hex

        ttl = int(
            getattr(
                self,
                "MEDIA_ENQUEUE_LOCK_TTL_SECONDS",
                300,
            )
            or 300
        )

        try:
            acquired = cache.add(
                key,
                token,
                timeout=ttl,
            )

            if not acquired:
                logger.info(
                    (
                        "⏭️ skip enqueue lock hit: "
                        "%s[%s] %s (%s)"
                    ),
                    self.__class__.__name__,
                    getattr(
                        self,
                        "pk",
                        None,
                    ),
                    field_name,
                    kind,
                )

                return None

            return key, token

        except Exception as exc:
            # Conversion must remain available even when
            # the cache backend is temporarily unavailable.
            logger.warning(
                (
                    "⚠️ enqueue lock unavailable for "
                    "%s[%s] %s (%s): %s"
                ),
                self.__class__.__name__,
                getattr(
                    self,
                    "pk",
                    None,
                ),
                field_name,
                kind,
                exc,
            )

            return "", ""


    def _release_enqueue_lock(
        self,
        lease: tuple[str, str] | None,
    ) -> None:
        """
        Release only the lease acquired by this enqueue attempt.

        The ownership token prevents an old enqueue attempt from
        deleting a newer lock after its own lease has expired.
        """

        if not lease:
            return

        key, token = lease

        if not key or not token:
            return

        try:
            current_token = cache.get(
                key
            )

            if current_token != token:
                return

            cache.delete(
                key
            )

        except Exception as exc:
            # TTL remains the final safety net.
            logger.warning(
                (
                    "⚠️ enqueue lock release failed for "
                    "%s[%s]: %s"
                ),
                self.__class__.__name__,
                getattr(
                    self,
                    "pk",
                    None,
                ),
                exc,
            )

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

    def _dispatch_conversion_task(
        self,
        *,
        job,
        task,
        task_kwargs,
        queue="video",
    ):
        countdown = int(
            getattr(
                self,
                "MEDIA_ENQUEUE_COUNTDOWN_SECONDS",
                2,
            )
            or 2
        )

        task_id = str(
            uuid.uuid4()
        )

        # Persist task identity before the broker
        # can make the task visible to a worker.
        attach_task(
            job,
            task_id,
            queue=queue,
        )

        try:
            return task.apply_async(
                kwargs=task_kwargs,
                queue=queue,
                countdown=countdown,
                task_id=task_id,
            )

        except Exception as exc:
            job.mark_failed(
                (
                    "Failed to enqueue media "
                    f"conversion: {exc}"
                )
            )

            raise

    def _enqueue_conversion_tasks(
        self,
    ):
        """
        Enqueue conversion tasks for the current media generation.

        This method runs only after commit.

        Field-level gates may delay individual media fields without blocking
        unrelated media on the same target.
        """

        if getattr(
            self,
            "is_converted",
            False,
        ):
            logger.info(
                "⏭️ skip enqueue: %s[%s] already converted",
                self.__class__.__name__,
                getattr(
                    self,
                    "pk",
                    None,
                ),
            )

            return

        scheduled_any = False

        for field_name, cfg in self.media_conversion_config.items():
            file_field = getattr(
                self,
                field_name,
                None,
            )

            if not file_field:
                continue

            try:
                upload, explicit_kind = (
                    self._resolve_upload_and_kind(
                        cfg,
                        field_name,
                    )
                )

                source_path = getattr(
                    file_field,
                    "name",
                    None,
                )

                if not source_path:
                    continue

                source_path = str(
                    source_path
                ).strip().lstrip(
                    "/"
                )

                if not source_path:
                    continue

                ext = os.path.splitext(
                    source_path
                )[1].lower()

                mime_type, _ = mimetypes.guess_type(
                    source_path
                )

                # -------------------------------------------------
                # Resolve media kind
                # -------------------------------------------------
                kind = explicit_kind

                if kind is None:
                    normalized_field_name = (
                        field_name.lower()
                    )

                    if normalized_field_name in (
                        "audio",
                        "voice",
                        "sound",
                    ):
                        kind = KIND_AUDIO

                    elif normalized_field_name in (
                        "video",
                        "movie",
                        "clip",
                    ):
                        kind = KIND_VIDEO

                    elif normalized_field_name in (
                        "thumbnail",
                        "thumb",
                        "image",
                        "photo",
                        "avatar",
                        "banner",
                    ):
                        kind = KIND_IMAGE

                if kind is None and mime_type:
                    if mime_type.startswith(
                        "image/"
                    ):
                        kind = KIND_IMAGE

                    elif mime_type.startswith(
                        "audio/"
                    ):
                        kind = KIND_AUDIO

                    elif mime_type.startswith(
                        "video/"
                    ):
                        kind = KIND_VIDEO

                if kind is None:
                    logger.warning(
                        (
                            "❓ Unable to infer kind for "
                            "%s.%s (mime=%s). Skipping."
                        ),
                        self.__class__.__name__,
                        field_name,
                        mime_type,
                    )

                    continue

                # -------------------------------------------------
                # Field-level pre-enqueue gate
                # -------------------------------------------------
                try:
                    enqueue_allowed = (
                        self.media_conversion_enqueue_allowed(
                            field_name=field_name,
                            kind=kind,
                            source_path=source_path,
                        )
                    )

                except Exception as exc:
                    logger.exception(
                        (
                            "❌ media conversion enqueue gate failed for "
                            "%s[%s].%s (%s): %s"
                        ),
                        self.__class__.__name__,
                        getattr(
                            self,
                            "pk",
                            None,
                        ),
                        field_name,
                        kind,
                        exc,
                    )

                    continue

                if not enqueue_allowed:
                    logger.info(
                        (
                            "⏸️ media conversion blocked by pre-enqueue gate: "
                            "%s[%s].%s (%s)"
                        ),
                        self.__class__.__name__,
                        getattr(
                            self,
                            "pk",
                            None,
                        ),
                        field_name,
                        kind,
                    )

                    continue

                # -------------------------------------------------
                # Duplicate protection
                # -------------------------------------------------
                if self._should_skip_duplicate_enqueue(
                    field_name,
                    kind,
                    source_path,
                ):
                    continue

                lease = self._acquire_enqueue_lock(
                    field_name,
                    kind,
                    source_path,
                )

                if lease is None:
                    continue

                try:
                    if self._should_skip_duplicate_enqueue(
                        field_name,
                        kind,
                        source_path,
                    ):
                        continue

                    # -------------------------------------------------
                    # Image
                    # -------------------------------------------------
                    if kind == KIND_IMAGE:
                        job = upsert_job(
                            instance=self,
                            field_name=field_name,
                            kind=KIND_IMAGE,
                            status=MediaJobStatus.QUEUED,
                            source_path=source_path,
                            message=(
                                "Queued for image processing"
                            ),
                        )

                        self._dispatch_conversion_task(
                            job=job,
                            task=convert_image_to_jpg_task,
                            queue="video",
                            task_kwargs={
                                "model_name": (
                                    self.__class__.__name__
                                ),
                                "app_label": (
                                    self._meta.app_label
                                ),
                                "instance_id": self.pk,
                                "field_name": field_name,
                                "source_path": source_path,
                                "fileupload": (
                                    upload.to_dict()
                                ),
                            },
                        )

                        scheduled_any = True

                    # -------------------------------------------------
                    # Audio
                    # -------------------------------------------------
                    elif kind == KIND_AUDIO:
                        if ext == ".mp3":
                            job = upsert_job(
                                instance=self,
                                field_name=field_name,
                                kind=KIND_AUDIO,
                                status=MediaJobStatus.DONE,
                                source_path=source_path,
                                message=(
                                    "Audio already in final format"
                                ),
                            )

                            scheduled_any = True

                            # Do not directly flip is_converted here.
                            #
                            # The same field-aware readiness aggregator used by
                            # worker-completed jobs must remain authoritative.
                            transaction.on_commit(
                                lambda job_id=job.pk: (
                                    maybe_mark_media_target_available_by_id(
                                        job_id
                                    )
                                )
                            )

                            logger.info(
                                (
                                    "✅ audio already canonical (.mp3) – "
                                    "DONE job recorded for %s[%s].%s"
                                ),
                                self.__class__.__name__,
                                getattr(
                                    self,
                                    "pk",
                                    None,
                                ),
                                field_name,
                            )

                            continue

                        job = upsert_job(
                            instance=self,
                            field_name=field_name,
                            kind=KIND_AUDIO,
                            status=MediaJobStatus.QUEUED,
                            source_path=source_path,
                            message=(
                                "Queued for audio processing"
                            ),
                        )

                        self._dispatch_conversion_task(
                            job=job,
                            task=convert_audio_to_mp3_task,
                            queue="video",
                            task_kwargs={
                                "model_name": (
                                    self.__class__.__name__
                                ),
                                "app_label": (
                                    self._meta.app_label
                                ),
                                "instance_id": self.pk,
                                "field_name": field_name,
                                "source_path": source_path,
                                "fileupload": (
                                    upload.to_dict()
                                ),
                            },
                        )

                        scheduled_any = True

                    # -------------------------------------------------
                    # Video
                    # -------------------------------------------------
                    elif kind == KIND_VIDEO:
                        is_hls_artifact = (
                            ext in (
                                ".m3u8",
                                ".ts",
                            )
                            or source_path.endswith(
                                "master.m3u8"
                            )
                            or mime_type in (
                                "application/vnd.apple.mpegurl",
                                "application/x-mpegURL",
                            )
                        )

                        if is_hls_artifact:
                            logger.info(
                                (
                                    "⏭️ skip video: HLS artifact "
                                    "detected (path=%s)"
                                ),
                                source_path,
                            )

                            continue

                        job = upsert_job(
                            instance=self,
                            field_name=field_name,
                            kind=KIND_VIDEO,
                            status=MediaJobStatus.QUEUED,
                            source_path=source_path,
                            message=(
                                "Queued for video processing"
                            ),
                        )

                        self._dispatch_conversion_task(
                            job=job,
                            task=convert_video_to_multi_hls_task,
                            queue="video",
                            task_kwargs={
                                "model_name": (
                                    self.__class__.__name__
                                ),
                                "app_label": (
                                    self._meta.app_label
                                ),
                                "instance_id": self.pk,
                                "field_name": field_name,
                                "source_path": source_path,
                                "fileupload": (
                                    upload.to_dict()
                                ),
                            },
                        )

                        scheduled_any = True

                finally:
                    self._release_enqueue_lock(
                        lease
                    )

            except Exception as exc:
                logger.warning(
                    (
                        "❌ Failed to dispatch conversion "
                        "for %s.%s: %s"
                    ),
                    self.__class__.__name__,
                    field_name,
                    exc,
                    exc_info=True,
                )

        if not scheduled_any:
            logger.info(
                (
                    "ℹ️ no conversion task scheduled "
                    "for %s[%s]"
                ),
                self.__class__.__name__,
                getattr(
                    self,
                    "pk",
                    None,
                ),
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