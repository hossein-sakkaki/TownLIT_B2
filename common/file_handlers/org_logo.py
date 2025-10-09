# common/file_handlers/org_logo.py
from common.file_handlers.base_mixins import BaseS3URLMixin
from django.conf import settings

class OrganizationLogoMixin(BaseS3URLMixin):
    """
    Expose S3 key + signed/public URL for Organization.logo as:
      - "logo_key"
      - "logo_url"
    """
    signed_fields = {
        "logo": getattr(settings, "DEFAULT_ORG_LOGO_URL", "/static/img/org-default.png")
    }

    # No rename needed; keep "logo_url" as is
    # (You can override to_representation to rename if you ever want "logo_image_url")
