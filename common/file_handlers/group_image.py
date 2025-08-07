from common.file_handlers.base_mixins import BaseS3URLMixin
from django.conf import settings


class GroupImageMixin(BaseS3URLMixin):
    """
    Mixin to provide signed/public URL for `group_image` in Dialogue model,
    and rename `group_image_url` to `group_image_signed_url` in output.
    """
    signed_fields = {
        'group_image': settings.DEFAULT_GROUP_AVATAR_URL
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Optionally rename the field for better clarity
        if 'group_image_url' in rep:
            rep['group_image_signed_url'] = rep.pop('group_image_url')

        return rep
