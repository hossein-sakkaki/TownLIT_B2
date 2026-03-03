# apps/posts/models/pray.py

import logging
from urllib.parse import quote

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db.models import Q

from utils.mixins.slug_mixin import SlugMixin
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin

from apps.core.visibility.mixins import VisibilityModelMixin
from apps.core.moderation.mixins import ModerationTargetMixin
from apps.core.interactions.mixins import InteractionCounterMixin
from apps.core.interactions.models import ReactionBreakdownMixin
from apps.core.availability.interfaces import AvailabilityAware

from utils.common.utils import FileUpload

from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.mediaValidators.video_validators import (
    validate_moment_video_file,  # reuse validator (safe default)
)
from validators.security_validators import validate_no_executable_file

from apps.core.visibility.constants import (
    VISIBILITY_PRIVATE,
    VISIBILITY_FRIENDS,
    VISIBILITY_COVENANT,
)

from apps.notifications.services.services import create_and_dispatch_notification

from apps.profiles.models import Friendship, Member
from apps.profiles.constants import ACCEPTED


logger = logging.getLogger(__name__)
User = get_user_model()


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class PrayerStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"
    ANSWERED = "answered", "Answered"
    NOT_ANSWERED = "not_answered", "Not Answered"


# -----------------------------------------------------------------------------
# Upload roots
# -----------------------------------------------------------------------------
PRAY_IMAGE = FileUpload("posts", "images", "pray")
PRAY_VIDEO = FileUpload("posts", "videos", "pray")



# -----------------------------------------------------------------------------
# Model: Prayer
# -----------------------------------------------------------------------------
class Prayer(
    ModerationTargetMixin,        # 🔐 moderation contract
    VisibilityModelMixin,         # 👁️ visibility
    InteractionCounterMixin,      # 🧮 counters
    ReactionBreakdownMixin,       # ❤️ reactions
    MediaAutoConvertMixin,        # 🎞 raw → converted detection
    MediaConversionMixin,         # 🔄 async conversion
    SlugMixin,
    AvailabilityAware,
    models.Model,
):
    # Thumbnail is user-provided (do not force auto)
    AUTO_THUMBNAIL_FROM_VIDEO = False

    id = models.BigAutoField(primary_key=True)

    # --- content ---
    caption = models.TextField(null=True, blank=True, verbose_name="Prayer Text")

    image = models.ImageField(
        upload_to=PRAY_IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name="Image",
    )

    video = models.FileField(
        upload_to=PRAY_VIDEO.dir_upload,
        null=True,
        blank=True,
        validators=[validate_moment_video_file, validate_no_executable_file],
        verbose_name="Video",
    )

    thumbnail = models.ImageField(
        upload_to=PRAY_IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name="Thumbnail",
    )

    # --- owner (polymorphic) ---
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # --- lifecycle ---
    status = models.CharField(
        max_length=24,
        choices=PrayerStatus.choices,
        default=PrayerStatus.WAITING,
        db_index=True,
    )
    answered_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # --- analytics (internal) ---
    view_count_internal = models.PositiveBigIntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    # --- timestamps ---
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)

    # --- media pipeline ---
    is_converted = models.BooleanField(default=False)

    url_name = "posts:prayer-detail"

    media_conversion_config = {
        "image": {"upload": PRAY_IMAGE, "kind": "image"},
        "video": {"upload": PRAY_VIDEO, "kind": "video"},
        "thumbnail": {"upload": PRAY_IMAGE, "kind": "image"},
    }

    # --- validation ---
    def clean(self):
        """
        Media rules:
        - Image is REQUIRED (acts as thumbnail)
        - Video is OPTIONAL
        """
        if not self.image:
            raise ValidationError("Prayer requires an image.")


    # --- helpers ---
    @property
    def has_response(self) -> bool:
        """True if a response exists."""
        return hasattr(self, "response") and self.response is not None

    # --- availability --- 
    def is_available(self) -> bool:
        """
        Availability policy (Prayer):
        - image-only -> available immediately
        - image + video -> available only after conversion
        - no media / video-only -> not available (image required)
        """

        # Image required (clean enforces this)
        if not self.image:
            return False

        # Image-only
        if not self.video:
            return True

        # Image + video
        return bool(self.is_converted)

    def on_available(self):
        """Trigger notifications when fully available."""
        from apps.notifications.signals.prayer_signals import notify_prayer_ready
        notify_prayer_ready(self)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        image_only = bool(self.image and not self.video)

        # Let MediaAutoConvertMixin run first
        super().save(*args, **kwargs)

        # ----------------------------------------
        # FIX: Image-only should always be converted
        # ----------------------------------------
        if image_only and not self.is_converted:
            type(self).objects.filter(pk=self.pk).update(is_converted=True)
            self.is_converted = True

        # ----------------------------------------
        # Availability trigger (image-only create)
        # ----------------------------------------
        if is_new and image_only:
            transaction.on_commit(lambda: self.on_available())
            
    # --- slug ---
    def get_slug_source(self):
        return f"pray-{self.published_at.strftime('%Y%m%d%H%M%S')}"

    def __str__(self):
        return f"Prayer #{self.pk}"

    class Meta:
        verbose_name = "Prayer"
        verbose_name_plural = "Prayers"
        indexes = [
            models.Index(fields=["visibility", "-published_at", "-id"], name="prayer_vis_pub_id_idx"),
            models.Index(fields=["content_type", "object_id", "published_at"], name="prayer_owner_pub_idx"),
            models.Index(fields=["is_active", "is_hidden", "published_at"], name="prayer_mod_pub_idx"),
            models.Index(fields=["status", "answered_at"], name="prayer_status_answered_idx"),
            models.Index(fields=["published_at"], name="prayer_pub_idx"),
        ]


# -----------------------------------------------------------------------------
# Model: PrayerResponse (OneToOne)
# -----------------------------------------------------------------------------
class PrayerResponse(
    MediaAutoConvertMixin,        # 🎞 raw → converted detection
    MediaConversionMixin,         # 🔄 async conversion
    AvailabilityAware,
    models.Model,
):
    AUTO_THUMBNAIL_FROM_VIDEO = False

    id = models.BigAutoField(primary_key=True)

    prayer = models.OneToOneField(
        Prayer,
        on_delete=models.CASCADE,      # hard cascade
        related_name="response",
    )

    # --- result ---
    result_status = models.CharField(
        max_length=24,
        choices=[(PrayerStatus.ANSWERED, "Answered"), (PrayerStatus.NOT_ANSWERED, "Not Answered")],
        db_index=True,
    )

    response_text = models.TextField(null=True, blank=True)

    # --- media ---
    image = models.ImageField(
        upload_to=PRAY_IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name="Response Image",
    )

    video = models.FileField(
        upload_to=PRAY_VIDEO.dir_upload,
        null=True,
        blank=True,
        validators=[validate_moment_video_file, validate_no_executable_file],
        verbose_name="Response Video",
    )

    thumbnail = models.ImageField(
        upload_to=PRAY_IMAGE.dir_upload,
        null=True,
        blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name="Response Thumbnail",
    )

    # --- timestamps ---
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)

    # --- media pipeline ---
    is_converted = models.BooleanField(default=False)

    media_conversion_config = {
        "image": {"upload": PRAY_IMAGE, "kind": "image"},
        "video": {"upload": PRAY_VIDEO, "kind": "video"},
        "thumbnail": {"upload": PRAY_IMAGE, "kind": "image"},
    }

    def clean(self):
        """
        Media rules (Response):
        - image is required
        - video is optional
        - image + video is allowed
        """
        if not self.image:
            raise ValidationError("PrayerResponse requires an image.")

    def is_available(self) -> bool:
        """
        Availability policy (PrayerResponse):
        - If image exists and NO video -> available immediately
        - If image exists and video exists -> available only after conversion
        - If no media (text-only) -> available (optional)
        """

        # text-only (optional)
        if not self.image and not self.video:
            return True

        # image is required for media responses
        if not self.image:
            return False

        # image-only
        if not self.video:
            return True

        # image + video
        return bool(self.is_converted)

    def on_available(self):
        """Trigger notifications when response becomes available."""
        try:
            from apps.notifications.signals.prayer_signals import notify_prayer_result_ready
            notify_prayer_result_ready(self.prayer, self)
        except Exception:
            logger.exception("[Pray] notify_prayer_result_ready failed")

    def _sync_parent_prayer(self):
        """Keep Prayer.status and Prayer.answered_at in sync."""
        prayer = self.prayer
        if not prayer:
            return

        prayer.status = self.result_status
        prayer.answered_at = timezone.now()
        prayer.updated_at = timezone.now()
        prayer.save(update_fields=["status", "answered_at", "updated_at"])

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        image_only = bool(self.image and not self.video)

        if self.pk is not None:
            self.updated_at = timezone.now()

        super().save(*args, **kwargs)

        # Defer parent sync until outer transaction commits
        transaction.on_commit(self._sync_parent_prayer)

        # Manual availability trigger for image-only create
        if is_new and image_only:
            transaction.on_commit(lambda: self.on_available())

    def delete(self, *args, **kwargs):
        """
        Delete response.
        Parent reset is deferred until commit.
        """
        prayer = self.prayer

        super().delete(*args, **kwargs)

        if prayer:
            def _reset_parent():
                prayer.status = PrayerStatus.WAITING
                prayer.answered_at = None
                prayer.updated_at = timezone.now()
                prayer.save(update_fields=["status", "answered_at", "updated_at"])

            transaction.on_commit(_reset_parent)

    def __str__(self):
        return f"PrayerResponse #{self.pk} -> Prayer #{self.prayer_id}"

    class Meta:
        verbose_name = "Prayer Response"
        verbose_name_plural = "Prayer Responses"
        indexes = [
            models.Index(fields=["created_at"], name="prayer_resp_created_idx"),
            models.Index(fields=["result_status"], name="prayer_resp_result_idx"),
        ]