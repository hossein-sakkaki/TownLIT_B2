# apps/posts/models/moment.py

import os
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid

from utils.mixins.slug_mixin import SlugMixin
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.media_assets import MediaAssetsMixin

from apps.media_conversion.models import MediaJobStatus
from apps.media_conversion.services.jobs import upsert_job
from apps.media_conversion.tasks.image import convert_moment_image_item_to_jpg_task

from apps.core.visibility.mixins import VisibilityModelMixin
from apps.core.moderation.mixins import ModerationTargetMixin
from apps.core.interactions.mixins import InteractionCounterMixin
from apps.core.interactions.models import ReactionBreakdownMixin
from apps.core.availability.interfaces import AvailabilityAware

from utils.common.utils import FileUpload

from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
    validate_moment_image_size,
    validate_moment_image_items_metadata,
)
from validators.mediaValidators.video_validators import validate_moment_video_file
from validators.security_validators import validate_no_executable_file
from apps.posts.constants.moments import (
    MOMENT_MEDIA_KIND_CHOICES,
    MOMENT_MEDIA_KIND_IMAGE,
    MOMENT_MEDIA_KIND_VIDEO,
    MOMENT_MAX_IMAGES,
)
import logging
logger = logging.getLogger(__name__)

class Moment(
    ModerationTargetMixin,        # 🔐 Sanctuary / moderation contract
    VisibilityModelMixin,         # 👁️ user-defined visibility
    InteractionCounterMixin,      # 🧮 counters
    ReactionBreakdownMixin,       # ❤️ reaction types
    MediaAssetsMixin,             # 🖼️ Media metadata
    MediaAutoConvertMixin,        # 🎞️ RAW → converted detection
    MediaConversionMixin,         # 🔄 async conversion
    SlugMixin,
    AvailabilityAware, 
    models.Model
):
    # -------------------------------------------------
    # Auto-thumbnailing
    # -------------------------------------------------
    AUTO_THUMBNAIL_FROM_VIDEO = True
    
    # -------------------------------------------------
    # Upload roots
    # -------------------------------------------------
    IMAGE = FileUpload("posts", "images", "moment")
    VIDEO = FileUpload("posts", "videos", "moment")

    id = models.BigAutoField(primary_key=True)

    # -------------------------------------------------
    # Content
    # -------------------------------------------------
    caption = models.TextField(
        null=True,
        blank=True,
        verbose_name="Caption"
    )

    image = models.ImageField(
        upload_to=IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_moment_image_size,
            validate_no_executable_file,
        ],
        verbose_name="Image",
    )

    video = models.FileField(
        upload_to=VIDEO.dir_upload,
        null=True,
        blank=True,
        validators=[
            validate_moment_video_file,
            validate_no_executable_file,
        ],
        verbose_name="Video",
    )   

    thumbnail = models.ImageField(
        upload_to=IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
        verbose_name="Thumbnail",
    )

    # -------------------------------------------------
    # Metadata
    # -------------------------------------------------
    media_kind = models.CharField(
        max_length=16,
        choices=MOMENT_MEDIA_KIND_CHOICES,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Media Kind",
    )

    image_items = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Image Items",
        help_text="Ordered image metadata for multi-photo Moments.",
    )

    cover_image_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name="Cover Image ID",
        help_text="Pinned image item used as the grid/profile cover.",
    )

    audio_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Audio Payload",
        help_text="Reserved for future slideshow music/audio metadata.",
    )
    
    # -------------------------------------------------
    # Polymorphic owner (Member / Organization / Guest)
    # -------------------------------------------------
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # -------------------------------------------------
    # Analytics (internal only)
    # -------------------------------------------------
    view_count_internal = models.PositiveBigIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    # -------------------------------------------------
    # Publishing
    # -------------------------------------------------
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)

    notification_dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Publication Notification Dispatched At",
        help_text=(
            "Persistent marker preventing the original Moment publication "
            "notification from being dispatched more than once."
        ),
    )

    # -------------------------------------------------
    # Media pipeline
    # -------------------------------------------------
    is_converted = models.BooleanField(default=False)

    url_name = "posts:moment-detail"

    media_conversion_config = {
        # Photo Moments are handled through image_items conversion below.
        # Keep video/thumbnail in the generic conversion pipeline.
        "video": {"upload": VIDEO, "kind": "video"},
        "thumbnail": {"upload": IMAGE, "kind": "image"},
    }

    # -------------------------------------------------
    # Media helpers
    # -------------------------------------------------
    def has_image_items(self) -> bool:
        return bool(self.normalized_image_items())

    def normalized_image_items(self) -> list[dict]:
        """
        Return valid image item dictionaries.
        """
        if not isinstance(self.image_items, list):
            return []

        return [
            item for item in self.image_items
            if isinstance(item, dict) and item.get("key")
        ]

    def cover_image_item(self) -> dict | None:
        """
        Return pinned image item or first image item.
        """
        items = self.normalized_image_items()
        if not items:
            return None

        if self.cover_image_id:
            for item in items:
                if str(item.get("id")) == str(self.cover_image_id):
                    return item

        return items[0]

    def cover_image_key(self) -> str | None:
        """
        Return storage key for cover image.
        """
        item = self.cover_image_item()
        if item and item.get("key"):
            return str(item["key"]).lstrip("/")

        if self.image and getattr(self.image, "name", None):
            return str(self.image.name).lstrip("/")

        return None

    def build_image_item(
        self,
        *,
        key: str,
        file_name: str | None = None,
        mime_type: str | None = None,
        size: int | None = None,
        order: int = 0,
        is_cover: bool = False,
    ) -> dict:
        """
        Build stable image metadata.
        """
        return {
            "id": uuid.uuid4().hex,
            "key": str(key).lstrip("/"),
            "file_name": file_name or "",
            "mime_type": mime_type or "",
            "size": int(size or 0),
            "order": int(order),
            "is_cover": bool(is_cover),
        }
        
    def _image_item_requires_conversion(self, item: dict) -> bool:
        """
        Return True when image item still needs processing.
        """

        key = str(item.get("key") or "").strip().lower()

        if not key:
            return False

        final_exts = (".jpg", ".jpeg", ".png")
        is_web_safe = key.endswith(final_exts)

        has_dimensions = bool(
            item.get("width")
            and item.get("height")
            and item.get("aspect_ratio")
        )

        variants = item.get("variants")
        has_variants = isinstance(variants, dict) and bool(
            variants.get("thumb")
            and variants.get("grid")
            and variants.get("feed")
        )

        return (not is_web_safe) or (not has_dimensions) or (not has_variants)

    def _all_image_items_final(self) -> bool:
        """
        Return True when all JSON-backed photos are processed.
        """

        items = self.normalized_image_items()

        if not items:
            return False

        return not any(
            self._image_item_requires_conversion(item)
            for item in items
        )

    def _mark_photo_moment_converted_if_ready(self):
        """
        Mark photo Moment converted when all image items are already final.
        """
        if self.media_kind != MOMENT_MEDIA_KIND_IMAGE:
            return

        if not self._all_image_items_final():
            return

        updated = type(self).objects.filter(
            pk=self.pk,
            is_converted=False,
        ).update(is_converted=True)

        if updated:
            self.is_converted = True
            transaction.on_commit(lambda: self.on_available())

    def _enqueue_image_item_conversion_jobs(self):
        """
        Enqueue conversion jobs for JSON-backed Moment photos.

        Generic MediaConversionMixin only sees FileField/ImageField.
        Multi-photo Moment stores photos in image_items JSON, so we enqueue
        image_items:<id> jobs here.
        """
        if self.media_kind != MOMENT_MEDIA_KIND_IMAGE:
            return

        items = self.normalized_image_items()
        if not items:
            return

        scheduled_any = False

        for item in items:
            item_id = str(item.get("id") or "").strip()
            source_path = str(item.get("key") or "").strip().lstrip("/")

            if not item_id or not source_path:
                continue

            if not self._image_item_requires_conversion(item):
                continue

            field_name = f"image_items:{item_id}"
            kind = "image"

            try:
                if self._should_skip_duplicate_enqueue(
                    field_name,
                    kind,
                    source_path,
                ):
                    continue

                if not self._acquire_enqueue_lock(
                    field_name,
                    kind,
                    source_path,
                ):
                    continue

                job = upsert_job(
                    instance=self,
                    field_name=field_name,
                    kind=kind,
                    status=MediaJobStatus.QUEUED,
                    source_path=source_path,
                    message="Queued for Moment photo processing",
                )

                self._dispatch_conversion_task(
                    job=job,
                    task=convert_moment_image_item_to_jpg_task,
                    queue="video",
                    task_kwargs={
                        "model_name": self.__class__.__name__,
                        "app_label": self._meta.app_label,
                        "instance_id": self.pk,
                        "field_name": field_name,
                        "source_path": source_path,
                        "fileupload": self.IMAGE.to_dict(),
                    },
                )

                scheduled_any = True

            except Exception:
                logger.exception(
                    "❌ Failed to enqueue Moment image item conversion: moment=%s field=%s path=%s",
                    self.pk,
                    field_name,
                    source_path,
                )

        if not scheduled_any:
            self._mark_photo_moment_converted_if_ready()
            
    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def clean(self):
        image_items = self.normalized_image_items()
        has_image = bool(self.image) or bool(image_items)
        has_video = bool(self.video)

        if has_image and has_video:
            raise ValidationError(
                "Moment can have either images or video, not both."
            )

        if not has_image and not has_video:
            raise ValidationError(
                "Moment requires at least one image or one video."
            )

        if has_video:
            if self.media_kind and self.media_kind != MOMENT_MEDIA_KIND_VIDEO:
                raise ValidationError("Video Moment must use video media kind.")

            if image_items:
                raise ValidationError("Video Moment cannot contain image items.")

            return

        if has_image:
            if self.media_kind and self.media_kind != MOMENT_MEDIA_KIND_IMAGE:
                raise ValidationError("Photo Moment must use image media kind.")

            total_images = len(image_items) if image_items else 1

            if total_images < 1:
                raise ValidationError("Photo Moment requires at least one image.")

            if total_images > MOMENT_MAX_IMAGES:
                raise ValidationError(
                    f"Photo Moment can contain up to {MOMENT_MAX_IMAGES} images."
                )

            if image_items:
                validate_moment_image_items_metadata(image_items)
            
    # -------------------------------------------------
    # Save override for availability and notifications
    # -------------------------------------------------
    def _media_state_snapshot(self) -> dict:
        """
        Return normalized persisted-media state for change detection.

        This state intentionally contains only fields whose changes should
        trigger Moment media processing.
        """
        return {
            "image": str(
                getattr(self.image, "name", "") or ""
            ),
            "video": str(
                getattr(self.video, "name", "") or ""
            ),
            "thumbnail": str(
                getattr(self.thumbnail, "name", "") or ""
            ),
            "image_items": (
                self.image_items
                if isinstance(self.image_items, list)
                else []
            ),
            "cover_image_id": (
                str(self.cover_image_id)
                if self.cover_image_id
                else None
            ),
            "media_kind": self.media_kind,
        }


    @staticmethod
    def _normalized_persisted_media_state(
        state: dict | None,
    ) -> dict | None:
        """
        Normalize a values() result to the same shape as
        _media_state_snapshot().
        """
        if state is None:
            return None

        image_items = state.get("image_items")

        return {
            "image": str(state.get("image") or ""),
            "video": str(state.get("video") or ""),
            "thumbnail": str(
                state.get("thumbnail") or ""
            ),
            "image_items": (
                image_items
                if isinstance(image_items, list)
                else []
            ),
            "cover_image_id": (
                str(state.get("cover_image_id"))
                if state.get("cover_image_id")
                else None
            ),
            "media_kind": state.get("media_kind"),
        }


    def _schedule_image_item_conversion_after_commit(self) -> None:
        """
        Reload the Moment after commit before entering the image-item pipeline.

        This avoids running conversion decisions from a stale in-memory instance.
        """
        moment_id = self.pk

        if not moment_id:
            return

        def _after_commit():
            fresh_moment = (
                type(self).objects
                .filter(pk=moment_id)
                .first()
            )

            if not fresh_moment:
                return

            fresh_moment._enqueue_image_item_conversion_jobs()

        transaction.on_commit(_after_commit)


    def save(self, *args, **kwargs):
        is_new = bool(self._state.adding)
        raw_update_fields = kwargs.get("update_fields")

        update_fields = (
            set(raw_update_fields)
            if raw_update_fields is not None
            else None
        )

        previous_media_state = None

        if not is_new and self.pk:
            previous = (
                type(self).objects
                .filter(pk=self.pk)
                .values(
                    "image",
                    "video",
                    "thumbnail",
                    "image_items",
                    "cover_image_id",
                    "media_kind",
                )
                .first()
            )

            previous_media_state = (
                self._normalized_persisted_media_state(
                    previous
                )
            )

        # Determine the canonical media kind.
        if self.video:
            self.media_kind = MOMENT_MEDIA_KIND_VIDEO
        elif self.image or self.has_image_items():
            self.media_kind = MOMENT_MEDIA_KIND_IMAGE

        # Legacy single image becomes a JSON-backed image item.
        if self.image and not self.has_image_items():
            key = getattr(self.image, "name", None)

            if key:
                item = self.build_image_item(
                    key=key,
                    file_name=str(key).split("/")[-1],
                    mime_type="",
                    size=0,
                    order=0,
                    is_cover=True,
                )

                self.image_items = [item]
                self.cover_image_id = item["id"]

        normalized_items = self.normalized_image_items()

        if normalized_items and not self.cover_image_id:
            self.cover_image_id = str(
                normalized_items[0]["id"]
            )

        current_media_state = self._media_state_snapshot()

        media_fields = {
            "image",
            "video",
            "thumbnail",
            "image_items",
            "cover_image_id",
            "media_kind",
        }

        update_touches_media = (
            update_fields is None
            or bool(update_fields & media_fields)
        )

        media_changed = (
            is_new
            or (
                update_touches_media
                and previous_media_state
                != current_media_state
            )
        )

        super().save(*args, **kwargs)

        is_photo_moment = (
            self.media_kind
            == MOMENT_MEDIA_KIND_IMAGE
        )

        if is_photo_moment and media_changed:
            self._schedule_image_item_conversion_after_commit()
            
    # -------------------------------------------------
    # Availability (Domain-level)
    # -------------------------------------------------
    def is_available(self) -> bool:
        """
        Moment is available when:
        - Photo Moment exists and all image items are final/converted.
        - OR video exists and conversion is finished.
        """
        if self.media_kind == MOMENT_MEDIA_KIND_IMAGE:
            return bool(self.image or self.has_image_items()) and bool(self.is_converted)

        if self.video and self.is_converted:
            return True

        return False

    def on_available(self):
        """
        Called when the moment becomes fully available.
        Responsible for triggering notifications.
        """
        from apps.notifications.signals.moment_signals import notify_moment_ready

        notify_moment_ready(self)


    def media_autoconvert_enabled(self) -> bool:
        """
        Keep generic conversion enabled for videos/thumbnails.

        Photo Moment image_items are converted by Moment-specific enqueue logic.
        """
        return True


    def get_slug_source(self):
        return f"moment-{self.published_at.strftime('%Y%m%d%H%M%S')}"

    def __str__(self):
        return f"Moment #{self.pk}"

    class Meta:
        verbose_name = "Moment"
        verbose_name_plural = "Moments"
        indexes = [
            models.Index(
                fields=["visibility", "-published_at", "-id"],
                name="moment_vis_pub_id_idx",
            ),
            models.Index(
                fields=["content_type", "object_id", "published_at"],
                name="moment_owner_pub_idx",
            ),
            models.Index(
                fields=["is_active", "is_hidden", "published_at"],
                name="moment_mod_pub_idx",
            ),
            models.Index(
                fields=["published_at"],
                name="moment_pub_idx",
            ),
        ]

