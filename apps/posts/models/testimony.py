from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from utils.common.utils import FileUpload
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.slug_mixin import SlugMixin

from validators.mediaValidators.audio_validators import validate_audio_file
from validators.mediaValidators.video_validators import validate_video_file
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()





# Testimony Models ------------------------------------------------------------------------------------------------------
class Testimony(MediaConversionMixin, MediaAutoConvertMixin, SlugMixin):
    TYPE_AUDIO = 'audio'
    TYPE_VIDEO = 'video'
    TYPE_WRITTEN = 'written'
    FILE_TYPE_CHOICES = (
        (TYPE_AUDIO, 'Audio'),
        (TYPE_VIDEO, 'Video'),
        (TYPE_WRITTEN, 'Written'),
    )

    # --- Upload roots ---
    THUMBNAIL = FileUpload('posts', 'photos', 'testimony')
    AUDIO = FileUpload('posts', 'audios', 'testimony')
    VIDEO = FileUpload('posts', 'videos', 'testimony')

    id = models.BigAutoField(primary_key=True)

    # NEW: type of testimony (enables one-per-type owner constraint)
    type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, db_index=True, verbose_name='Type')

    title = models.CharField(max_length=50, null=True, blank=True, verbose_name='Title')
    content = models.TextField(null=True, blank=True, verbose_name='Testimony Content')

    audio = models.FileField(
        upload_to=AUDIO.dir_upload, null=True, blank=True,
        validators=[validate_audio_file, validate_no_executable_file],
        verbose_name='Testimony Audio'
    )
    video = models.FileField(
        upload_to=VIDEO.dir_upload, null=True, blank=True,
        validators=[validate_video_file, validate_no_executable_file],
        verbose_name='Testimony Video'
    )
    thumbnail = models.ImageField(
        upload_to=THUMBNAIL.dir_upload, null=True, blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name='Thumbnail 1'
    )

    org_tags = models.ManyToManyField(
        'profilesOrg.Organization', blank=True, related_name='tagged_in_testimonies', db_index=True,
        verbose_name='Organization Tags'
    )
    user_tags = models.ManyToManyField(
        CustomUser, blank=True, related_name='tagged_in_testimonies', db_index=True,
        verbose_name='User Tags'
    )

    # Polymorphic owner (Member, Organization, …)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Moderation / visibility
    is_suspended = models.BooleanField(default=False, verbose_name="Is Suspended")
    reports_count = models.IntegerField(default=0, verbose_name="Reports Count")
    is_restricted = models.BooleanField(default=False, verbose_name='Restricted')
    is_hidden = models.BooleanField(default=False, verbose_name='Is Hidden')
    is_active = models.BooleanField(default=True, verbose_name='Is Active')

    # Publishing
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Published Date')
    updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Updated Date')

    # Optional flag used by converter tasks (mirrors your OfficialVideo pattern)
    is_converted = models.BooleanField(default=False)

    url_name = 'posts:testimony-detail'

    # Tell the converter which fields to process and their upload roots
    media_conversion_config = {
        "audio":     {"upload": AUDIO,     "kind": "audio"},
        "video":     {"upload": VIDEO,     "kind": "video"},
        "thumbnail": {"upload": THUMBNAIL, "kind": "image"},
    }

    # --- change tracking for re-conversion on updates ---
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_audio = getattr(self.audio, 'name', None)
        self._orig_video = getattr(self.video, 'name', None)
        self._orig_thumb = getattr(self.thumbnail, 'name', None)

    def _media_changed(self) -> bool:
        """Detect if any media field filename changed."""
        return any([
            getattr(self.audio, 'name', None) != self._orig_audio,
            getattr(self.video, 'name', None) != self._orig_video,
            getattr(self.thumbnail, 'name', None) != self._orig_thumb,
        ])

    # --- validation rules by type ---            
    def clean(self):
        if self.type == self.TYPE_WRITTEN:
            if not self.content or self.audio or self.video:
                raise ValidationError("Written testimony requires content and no audio/video.")
            if not self.title or not self.title.strip():
                raise ValidationError("Written testimony requires a title.")
        elif self.type == self.TYPE_AUDIO:
            if not self.audio or self.content or self.video:
                raise ValidationError("Audio testimony requires an audio file and no text/video.")
        elif self.type == self.TYPE_VIDEO:
            if not self.video or self.content or self.audio:
                raise ValidationError("Video testimony requires a video file and no text/audio.")
        else:
            raise ValidationError("Invalid testimony type.")

    # --- ensure non-empty title for slug source ---
    def _ensure_default_title(self):
        if self.type == self.TYPE_WRITTEN:
            return

        if self.title and self.title.strip():
            return

        type_label = dict(self.FILE_TYPE_CHOICES).get(self.type, self.type).title()
        owner_name = None
        try:
            if hasattr(self.content_object, "user") and getattr(self.content_object.user, "username", None):
                owner_name = self.content_object.user.username
            elif hasattr(self.content_object, "name") and self.content_object.name:
                owner_name = self.content_object.name
        except Exception:
            pass

        if owner_name:
            self.title = f"{type_label} testimony by {owner_name}"
        else:
            self.title = f"{type_label} testimony {timezone.now().strftime('%Y%m%d-%H%M%S')}"

    def on_media_converted(self, field_name: str, update_fields: list[str]) -> None:
        if field_name in ("audio", "video"):
            if not self.is_active:
                self.is_active = True
                update_fields.append("is_active")

    def get_slug_source(self):
        """Never return empty; SlugMixin relies on this."""
        if self.title and self.title.strip():
            return self.title
        return f"{self.type}-testimony-{(self.published_at or timezone.now()).strftime('%Y%m%d-%H%M%S')}"

    def before_autoconvert_save(self):
        self._ensure_default_title()
        
    def __str__(self):
        return f"{self.title} [{self.type}]"

    class Meta:
        verbose_name = "Testimony"
        verbose_name_plural = "Testimonies"
        constraints = [
            # One testimony of a given type per owner (content_object)
            models.UniqueConstraint(
                fields=['content_type', 'object_id', 'type'],
                name='uniq_owner_type_testimony'
            ),
        ]
        
