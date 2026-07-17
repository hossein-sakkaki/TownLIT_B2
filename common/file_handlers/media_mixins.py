# common/file_handlers/media_mixins.py
from django.conf import settings
from common.file_handlers.base_mixins import BaseS3URLMixin


def _get_setting(name: str, default=None):
    return getattr(settings, name, default)


# Audio File Mixin --------------------------------------------------------------------------------
class AudioFileMixin(BaseS3URLMixin):
    """
    Provides signed/public URL for an `audio` FileField.
    Adds: audio_key, audio_url  -> and renames audio_url -> audio_signed_url
    Default placeholder can be set via settings.DEFAULT_AUDIO_PLACEHOLDER_URL
    """
    signed_fields = {
        'audio': _get_setting('DEFAULT_AUDIO_PLACEHOLDER_URL', None)
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if 'audio_url' in rep:
            rep['audio_signed_url'] = rep.pop('audio_url')
        return rep


# Video File Mixin --------------------------------------------------------------------------------
class VideoFileMixin(BaseS3URLMixin):
    """
    Provides signed/public URL for a `video` FileField.
    Adds: video_key, video_url  -> and renames video_url -> video_signed_url
    Default placeholder can be set via settings.DEFAULT_VIDEO_PLACEHOLDER_URL
    """
    signed_fields = {
        'video': _get_setting('DEFAULT_VIDEO_PLACEHOLDER_URL', None)
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if 'video_url' in rep:
            rep['video_signed_url'] = rep.pop('video_url')
        return rep


# Thumbnail File Mixin ----------------------------------------------------------------------------
class ThumbnailFileMixin(BaseS3URLMixin):
    """Signed/public URL for single `thumbnail` field."""
    signed_fields = {
        'thumbnail': getattr(settings, 'DEFAULT_THUMB_LACEHOLDER_URL', None),
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if 'thumbnail_url' in rep:
            rep['thumbnail_signed_url'] = rep.pop('thumbnail_url')
        return rep


# Audio Artwork File Mixin -------------------------------------------------------------------------
class AudioArtworkFileMixin(BaseS3URLMixin):
    """
    Signed/public URL for Testimony `audio_artwork` field.

    Adds:
      - audio_artwork_key
      - audio_artwork_url

    Then renames:
      - audio_artwork_url -> audio_artwork_signed_url

    This keeps audio artwork aligned with thumbnail/audio/video media contracts.
    """
    signed_fields = {
        "audio_artwork": _get_setting("DEFAULT_AUDIO_ARTWORK_PLACEHOLDER_URL", None),
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if "audio_artwork_url" in rep:
            rep["audio_artwork_signed_url"] = rep.pop("audio_artwork_url")

        return rep
    
    
# Image File Mixin --------------------------------------------------------------------------------
class ImageFileMixin(BaseS3URLMixin):
    """
    Provides signed/public URL for an `image` ImageField.
    Adds:
      - image_key
      - image_signed_url  (renamed from image_url)

    Default placeholder can be set via:
      settings.DEFAULT_IMAGE_PLACEHOLDER_URL
    """
    signed_fields = {
        'image': _get_setting('DEFAULT_IMAGE_PLACEHOLDER_URL', None)
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if 'image_url' in rep:
            rep['image_signed_url'] = rep.pop('image_url')
        return rep