# common/file_handlers/media_mixins.py
from django.conf import settings
from common.file_handlers.base_mixins import BaseS3URLMixin


def _get_setting(name: str, default=None):
    return getattr(settings, name, default)


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


class TestimonyThumbnailMixin(BaseS3URLMixin):
    """Signed/public URL for single `thumbnail` field."""
    signed_fields = {
        'thumbnail': getattr(settings, 'DEFAULT_TESTIMONY_THUMB_URL', None),
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if 'thumbnail_url' in rep:
            rep['thumbnail_signed_url'] = rep.pop('thumbnail_url')
        return rep
