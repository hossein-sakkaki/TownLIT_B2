# apps/posts/models/testimony.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from utils.common.utils import FileUpload
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.slug_mixin import SlugMixin

from apps.core.visibility.mixins import VisibilityModelMixin
from apps.core.moderation.mixins import ModerationTargetMixin

# 🔥 NEW: Interactions
from apps.core.interactions.mixins import InteractionCounterMixin
from apps.core.interactions.models import ReactionBreakdownMixin

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
    MediaAutoConvertMixin,
    MediaConversionMixin,
    SlugMixin,
    models.Model,
):
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
    }

    # -------------------------------------------------
    # Change tracking (for reconvert)
    # -------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_audio = getattr(self.audio, "name", None)
        self._orig_video = getattr(self.video, "name", None)
        self._orig_thumb = getattr(self.thumbnail, "name", None)

    def _media_changed(self) -> bool:
        return any([
            getattr(self.audio, "name", None) != self._orig_audio,
            getattr(self.video, "name", None) != self._orig_video,
            getattr(self.thumbnail, "name", None) != self._orig_thumb,
        ])

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def clean(self):
        if self.type == self.TYPE_WRITTEN:
            if not self.content or self.audio or self.video:
                raise ValidationError(
                    "Written testimony requires content and no audio/video."
                )
            if not self.title or not self.title.strip():
                raise ValidationError(
                    "Written testimony requires a title."
                )

        elif self.type == self.TYPE_AUDIO:
            if not self.audio or self.content or self.video:
                raise ValidationError(
                    "Audio testimony requires audio only."
                )

        elif self.type == self.TYPE_VIDEO:
            if not self.video or self.content or self.audio:
                raise ValidationError(
                    "Video testimony requires video only."
                )

        else:
            raise ValidationError("Invalid testimony type.")

    # -------------------------------------------------
    # Slug + defaults
    # -------------------------------------------------
    def _ensure_default_title(self):
        if self.type == self.TYPE_WRITTEN:
            return
        if self.title and self.title.strip():
            return

        label = dict(self.FILE_TYPE_CHOICES).get(self.type, self.type).title()
        self.title = f"{label} testimony {timezone.now().strftime('%Y%m%d-%H%M%S')}"

    def before_autoconvert_save(self):
        self._ensure_default_title()

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
