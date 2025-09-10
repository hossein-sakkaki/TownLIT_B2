# common/file_handlers/document_file.py
import os
from typing import Dict, Any, Optional

from django.conf import settings
from common.aws.s3_utils import get_file_url, get_file_size
from common.file_handlers.base_mixins import BaseS3URLMixin

class DocumentFileMixin(BaseS3URLMixin):
    """
    Extends BaseS3URLMixin:
    - for each `field` in `signed_fields`, adds:
        <field>_key    : S3 key (already from BaseS3URLMixin)
        <field>_url    : presigned/public URL (already from BaseS3URLMixin, but with extra opts)
        <field>_name   : basename of key (for UI)
        <field>_size   : file size (bytes) via HEAD (best-effort)
    - supports per-field options via context:
        context["file_url_opts"] = {
            "<field>": {"expires_in": 600, "force_download": False}
        }
    """
    signed_fields: Dict[str, Optional[str]] = {}

    def to_representation(self, instance):
        rep = super().to_representation(instance)  # builds *_key and *_url (basic)
        request = self.context.get("request")
        url_opts: Dict[str, Dict[str, Any]] = self.context.get("file_url_opts", {}) or {}

        for field, default in self.signed_fields.items():
            # read S3 key
            file = getattr(instance, field, None)
            key = getattr(file, "name", None) or None

            # rebuild URL with custom opts (expires_in/force_download) if provided
            if key:
                opts = url_opts.get(field, {})
                url = get_file_url(
                    key=key,
                    default_url=default,
                    expires_in=opts.get("expires_in"),
                    force_download=opts.get("force_download", False),
                )
            else:
                url = default

            # absolute URL if request exists and url is relative
            if request and url and not (str(url).startswith("http://") or str(url).startswith("https://")):
                url = request.build_absolute_uri(url)

            # overwrite the *_url produced by BaseS3URLMixin with the one holding opts
            rep[f"{field}_key"] = key
            rep[f"{field}_url"] = url

            # add UI-friendly name and size
            rep[f"{field}_name"] = os.path.basename(key) if key else None
            try:
                rep[f"{field}_size"] = get_file_size(key) if key else None
            except Exception:
                rep[f"{field}_size"] = None  # non-fatal

        return rep
