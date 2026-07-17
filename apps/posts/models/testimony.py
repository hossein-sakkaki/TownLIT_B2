# apps/posts/models/testimony.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from utils.common.utils import FileUpload
from utils.mixins.media_assets import MediaAssetsMixin
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.slug_mixin import SlugMixin

from apps.core.visibility.mixins import VisibilityModelMixin
from apps.core.moderation.mixins import ModerationTargetMixin

# 🔥 NEW: Interactions
from apps.core.interactions.mixins import InteractionCounterMixin
from apps.core.interactions.models import ReactionBreakdownMixin

from apps.core.availability.interfaces import AvailabilityAware

from validators.mediaValidators.audio_validators import validate_audio_file
from validators.mediaValidators.video_validators import validate_testimony_video_file
from validators.mediaValidators.image_validators import (
    validate_image_file,
    validate_image_size,
)
from validators.security_validators import validate_no_executable_file

from django.contrib.auth import get_user_model
CustomUser = get_user_model()


class Testimony(
    ModerationTargetMixin,        # 🔐 Sanctuary / reporting / moderation
    VisibilityModelMixin,         # 👁️ visibility + is_hidden
    InteractionCounterMixin,      # 💬 comments / recomments / reactions_count
    ReactionBreakdownMixin,       # ❤️ per-reaction-type counters
    MediaAssetsMixin,             # 🖼️ Media metadata
    MediaAutoConvertMixin,
    MediaConversionMixin,
    SlugMixin,
    AvailabilityAware,
    models.Model,
):
  
    AUTO_THUMBNAIL_FROM_VIDEO = False

    # -------------------------------------------------
    # Types
    # -------------------------------------------------
    TYPE_AUDIO = "audio"
    TYPE_VIDEO = "video"
    TYPE_WRITTEN = "written"

    FILE_TYPE_CHOICES = (
        (TYPE_AUDIO, "Audio"),
        (TYPE_VIDEO, "Video"),
        (TYPE_WRITTEN, "Written"),
    )

    # -------------------------------------------------
    # Upload roots
    # -------------------------------------------------
    THUMBNAIL = FileUpload("posts", "photos", "testimony")
    AUDIO = FileUpload("posts", "audios", "testimony")
    VIDEO = FileUpload("posts", "videos", "testimony")
    AUDIO_ARTWORK = FileUpload("posts", "artworks", "testimony")

    id = models.BigAutoField(primary_key=True)

    # -------------------------------------------------
    # Core content
    # -------------------------------------------------
    type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        db_index=True,
        verbose_name="Type",
    )

    title = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Title", 
    )

    content = models.TextField(
        null=True,
        blank=True,
        verbose_name="Testimony Content",
    )

    audio = models.FileField(
        upload_to=AUDIO.dir_upload,
        null=True,
        blank=True,
        validators=[validate_audio_file, validate_no_executable_file],
        verbose_name="Testimony Audio",
    )

    video = models.FileField(
        upload_to=VIDEO.dir_upload,
        null=True,
        blank=True,
        validators=[validate_testimony_video_file, validate_no_executable_file],
        verbose_name="Testimony Video",
    )

    thumbnail = models.ImageField(
        upload_to=THUMBNAIL.dir_upload,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
        verbose_name="Thumbnail",
    )

    audio_artwork = models.ImageField(
        upload_to=AUDIO_ARTWORK.dir_upload,
        null=True,
        blank=True,
        validators=[
            validate_image_file,
            validate_image_size,
            validate_no_executable_file,
        ],
        verbose_name="Audio Artwork",
    )

    # -------------------------------------------------
    # Tags
    # -------------------------------------------------
    org_tags = models.ManyToManyField(
        "profilesOrg.Organization",
        blank=True,
        related_name="tagged_in_testimonies",
        db_index=True,
    )

    user_tags = models.ManyToManyField(
        CustomUser,
        blank=True,
        related_name="tagged_in_testimonies",
        db_index=True,
    )

    # -------------------------------------------------
    # Polymorphic owner (Member / Org / Guest)
    # -------------------------------------------------
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # -------------------------------------------------
    # Analytics (views)
    # -------------------------------------------------
    view_count_internal = models.PositiveIntegerField(
        default=0,
        verbose_name="Internal View Count",
    )

    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Last Viewed At",
    )

    # -------------------------------------------------
    # Publishing / feed
    # -------------------------------------------------
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    # -------------------------------------------------
    # Media pipeline
    # -------------------------------------------------
    is_converted = models.BooleanField(default=False)

    url_name = "posts:testimony-detail"

    media_conversion_config = {
        "audio": {"upload": AUDIO, "kind": "audio"},
        "video": {"upload": VIDEO, "kind": "video"},
        "thumbnail": {"upload": THUMBNAIL, "kind": "image"},
        "audio_artwork": {"upload": AUDIO_ARTWORK, "kind": "image"},
    }

    # -------------------------------------------------
    # Change tracking (for reconvert)
    # -------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_audio = getattr(self.audio, "name", None)
        self._orig_video = getattr(self.video, "name", None)
        self._orig_thumb = getattr(self.thumbnail, "name", None)
        self._orig_audio_artwork = getattr(self.audio_artwork, "name", None)

    def _media_changed(self) -> bool:
        return any([
            getattr(self.audio, "name", None) != self._orig_audio,
            getattr(self.video, "name", None) != self._orig_video,
            getattr(self.thumbnail, "name", None) != self._orig_thumb,
            getattr(self.audio_artwork, "name", None) != self._orig_audio_artwork,
        ])

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def clean(self):
        if self.type == self.TYPE_WRITTEN:
            if (
                not self.content
                or self.audio
                or self.video
                or self.thumbnail
                or self.audio_artwork
            ):
                raise ValidationError(
                    "Written testimony requires content and no media files."
                )

            if not self.title or not self.title.strip():
                raise ValidationError(
                    "Written testimony requires a title."
                )

        elif self.type == self.TYPE_AUDIO:
            if not self.audio or self.content or self.video or self.thumbnail:
                raise ValidationError(
                    "Audio testimony requires audio only. Optional audio_artwork is allowed."
                )

            if not self.title or not self.title.strip():
                raise ValidationError(
                    "Audio testimony requires a title."
                )

            if len(self.title.strip()) > 50:
                raise ValidationError(
                    "Audio testimony title must be 50 characters or fewer."
                )

        elif self.type == self.TYPE_VIDEO:
            if not self.video or self.content or self.audio or self.audio_artwork:
                raise ValidationError(
                    "Video testimony requires video only. Optional thumbnail is allowed."
                )

        else:
            raise ValidationError("Invalid testimony type.")

    # -------------------------------------------------
    # Availability (Domain-level)
    # -------------------------------------------------
    def is_available(self) -> bool:
        """
        Testimony is available when:
        - Written → always available
        - Audio → audio exists AND converted
        - Video → video exists AND converted
        """
        if self.type == self.TYPE_WRITTEN:
            return True

        if self.type == self.TYPE_AUDIO and self.audio and self.is_converted:
            return True

        if self.type == self.TYPE_VIDEO and self.video and self.is_converted:
            return True

        return False

    def on_available(self):
        """
        Called once when testimony becomes available.
        Responsible for triggering notifications.
        """

        # Prevent duplicate execution on the same in-memory instance.
        if getattr(self, "_availability_fired", False):
            return

        from apps.notifications.signals.testimony_signals import notify_testimony_ready
        notify_testimony_ready(self)

        from apps.subtitles.hooks import maybe_start_transcript_for_testimony
        maybe_start_transcript_for_testimony(self)

        # in-memory guard (same transaction / process)
        self._availability_fired = True

    # -------------------------------------------------
    # Autoconvert
    # -------------------------------------------------
    def media_autoconvert_enabled(self) -> bool:
        return self.type != self.TYPE_WRITTEN

    def before_autoconvert_save(self):
        # Written testimony has no conversion.
        # Media testimony titles must be provided by the user.
        if self.type == self.TYPE_WRITTEN:
            self.is_converted = True

    def after_autoconvert_save(self, *, is_new: bool, raw_changed: bool) -> None:
        if self.type != self.TYPE_WRITTEN:
            return
        if not is_new:
            return

        transaction.on_commit(lambda: self.on_available())

    # -------------------------------------------------
    # Slug + defaults
    # -------------------------------------------------
    def get_slug_source(self):
        if self.title and self.title.strip():
            return self.title
        return f"{self.type}-testimony-{self.published_at.strftime('%Y%m%d%H%M%S')}"

    def on_media_converted(self, field_name: str, update_fields: list[str]) -> None:
        if field_name in ("audio", "video") and not self.is_active:
            self.is_active = True
            update_fields.append("is_active")

    def __str__(self):
        return f"{self.title} [{self.type}]"

    class Meta:
        verbose_name = "Testimony"
        verbose_name_plural = "Testimonies"

        # 🔐 each owner can only have ONE testimony per type
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "type"],
                name="uniq_owner_type_testimony",
            ),
        ]

        # ⚡ feed / visibility / analytics indexes
        indexes = [
            models.Index(fields=["visibility", "published_at"]),
            models.Index(fields=["type", "published_at"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["published_at"]),
        ]
