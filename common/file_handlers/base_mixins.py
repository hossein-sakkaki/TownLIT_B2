# common/file_handlers/base_mixins.py

from common.aws.s3_utils import get_file_url

class BaseS3URLMixin:
    """
    For each entry in `signed_fields = { <field_name>: <default_url> }`,
    add:
      - "<field_name>_key" -> S3 object key (e.g., "accounts/photos/.../x.jpg") or None
      - "<field_name>_url" -> presigned/public URL (absolute if request exists)
    """
    signed_fields = {}

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')

        for field, default in self.signed_fields.items():
            file = getattr(instance, field, None)
            key = getattr(file, 'name', None) or None  # ensure None if empty

            # build URL with backend policy (presigned/public)
            url = get_file_url(key=key, default_url=default)

            # absolute URL if we have request context and url is relative
            if request and url and not (url.startswith("http://") or url.startswith("https://")):
                url = request.build_absolute_uri(url)

            rep[f"{field}_key"] = key
            rep[f"{field}_url"] = url

        return rep
