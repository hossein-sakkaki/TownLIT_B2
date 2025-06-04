# common/file_handlers/base_mixins.py

from common.aws.s3_utils import get_file_url
from django.conf import settings


class BaseS3URLMixin:
    signed_fields = {}  # Dict[str, str] => {'image': 'default_path'}

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        for field, default in self.signed_fields.items():
            file = getattr(instance, field, None)
            key = getattr(file, 'name', None)
            url = get_file_url(key=key, default_url=default)
            request = self.context.get('request')
            rep[f"{field}_url"] = request.build_absolute_uri(url) if request else url

        return rep
