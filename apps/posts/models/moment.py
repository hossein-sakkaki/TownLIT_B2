# apps/posts/models/moment.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from utils.common.utils import FileUpload
from utils.mixins.media_conversion import MediaConversionMixin
from utils.mixins.media_autoconvert import MediaAutoConvertMixin
from utils.mixins.slug_mixin import SlugMixin

from validators.mediaValidators.video_validators import validate_video_file
from validators.mediaValidators.image_validators import validate_image_file, validate_image_size
from validators.security_validators import validate_no_executable_file

import logging
logger = logging.getLogger(__name__)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# Moment Models ----------------------------------------------------------------------------------------------------------
class Moment(
    MediaAutoConvertMixin,
    MediaConversionMixin,
    SlugMixin,
    models.Model
):
    # Upload roots
    IMAGE = FileUpload('posts', 'images', 'moment')
    VIDEO = FileUpload('posts', 'videos', 'moment')

    id = models.BigAutoField(primary_key=True)

    caption = models.TextField(
        null=True, blank=True, verbose_name="Caption"
    )

    image = models.ImageField(
        upload_to=IMAGE.dir_upload,
        null=True, blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name="Moment Image"
    )

    video = models.FileField(
        upload_to=VIDEO.dir_upload,
        null=True, blank=True,
        validators=[validate_video_file, validate_no_executable_file],
        verbose_name="Moment Video"
    )

    thumbnail = models.ImageField(
        upload_to=IMAGE.dir_upload,
        null=True, blank=True,
        validators=[validate_image_file, validate_image_size, validate_no_executable_file],
        verbose_name="Thumbnail"
    )

    # tags
    org_tags = models.ManyToManyField(
        'profilesOrg.Organization',
        blank=True, related_name='tagged_in_moments', db_index=True
    )
    user_tags = models.ManyToManyField(
        CustomUser,
        blank=True, related_name='tagged_in_moments', db_index=True
    )

    # polymorphic owner
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    # moderation
    is_suspended = models.BooleanField(default=False)
    reports_count = models.IntegerField(default=0)
    is_restricted = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # publishing
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(null=True, blank=True)

    # media pipeline
    is_converted = models.BooleanField(default=False)

    url_name = "posts:moment-detail"

    media_conversion_config = {
        "image":     {"upload": IMAGE, "kind": "image"},
        "video":     {"upload": VIDEO, "kind": "video"},
        "thumbnail": {"upload": IMAGE, "kind": "image"},
    }

    def clean(self):
        if self.image and self.video:
            raise ValidationError("Moment can have either image or video, not both.")
        if not self.image and not self.video:
            raise ValidationError("Moment requires an image or a video.")

    def get_slug_source(self):
        owner = getattr(self.content_object, "user", None)
        base = owner.username if owner else "moment"
        return f"{base}-{self.published_at.strftime('%Y%m%d%H%M%S')}"

    def __str__(self):
        return f"Moment {self.pk}"

    class Meta:
        verbose_name = "Moment"
        verbose_name_plural = "Moments"
        indexes = [
            models.Index(fields=["published_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]
