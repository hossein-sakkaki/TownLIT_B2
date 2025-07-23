# common/file_handlers/profile_image.py

from common.file_handlers.base_mixins import BaseS3URLMixin
from django.conf import settings


class ProfileImageMixin(BaseS3URLMixin):
    """
    Mixin to provide signed/public URL for `image_name` (profile image),
    and rename `image_name_url` → `profile_image_url` in representation.
    """
    signed_fields = {
        # 'image_name': settings.MEDIA_URL + 'sample/user.png'
        'image_name': 'sample/user.png'
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Rename image_name_url to profile_image_url if exists
        if 'image_name_url' in rep:
            rep['profile_image_url'] = rep.pop('image_name_url')

        return rep