# apps/posts/models/moment.py

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from utils.mixins.slug_mixin import SlugMixin
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin

from apps.core.visibility.mixins import VisibilityModelMixin
from apps.core.moderation.mixins import ModerationTargetMixin
from apps.core.interactions.mixins import InteractionCounterMixin
from apps.core.interactions.models import ReactionBreakdownMixin
from apps.core.availability.interfaces import AvailabilityAware

from utils.common.utils import FileUpload

from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.mediaValidators.video_validators import validate_moment_video_file
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)

class Moment(
    ModerationTargetMixin,        # 🔐 Sanctuary / moderation contract
    VisibilityModelMixin,         # 👁️ user-defined visibility
    InteractionCounterMixin,      # 🧮 counters
    ReactionBreakdownMixin,       # ❤️ reaction types
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
            validate_image_size,
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

    # -------------------------------------------------
    # Media pipeline
    # -------------------------------------------------
    is_converted = models.BooleanField(default=False)

    url_name = "posts:moment-detail"

    media_conversion_config = {
        "image": {"upload": IMAGE, "kind": "image"},
        "video": {"upload": VIDEO, "kind": "video"},
        "thumbnail": {"upload": IMAGE, "kind": "image"},
    }

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def clean(self):
        if self.image and self.video:
            raise ValidationError(
                "Moment can have either image or video, not both."
            )
        if not self.image and not self.video:
            raise ValidationError(
                "Moment requires an image or a video."
            )

    # -------------------------------------------------
    # Save override for availability and notifications
    # -------------------------------------------------
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        image_only = bool(self.image and not self.video)

        super().save(*args, **kwargs)

        # Image-only moments are immediately final
        if image_only and not self.is_converted:
            type(self).objects.filter(pk=self.pk).update(is_converted=True)
            self.is_converted = True

        # Trigger notifications only after DB commit
        if is_new and image_only:
            transaction.on_commit(lambda: self.on_available())
            
    # -------------------------------------------------
    # Availability (Domain-level)
    # -------------------------------------------------
    def is_available(self) -> bool:
        """
        Moment is available when:
        - Image exists (immediate)
        - OR video exists AND conversion is finished
        """
        if self.image:
            return True

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
        Disable auto-conversion when Moment is image-only.
        Images (.jpg/.png/.jpeg) are already final and do not require pipeline.
        """
        if self.image and not self.video:
            # image-only moment → already final
            self.is_converted = True
            return False

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

