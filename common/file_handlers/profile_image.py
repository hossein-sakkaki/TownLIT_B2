# common/file_handlers/profile_image.py

from common.file_handlers.base_mixins import BaseS3URLMixin
from django.conf import settings


class ProfileImageMixin(BaseS3URLMixin):
    """
    Mixin to add signed/public URL for image_name field (profile picture).
    """

    signed_fields = {
        # 'image_name': settings.MEDIA_URL + 'sample/user.png'
        'image_name': 'sample/user.png'
    }
