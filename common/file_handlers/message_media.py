# common/file_handlers/message_media.py

from common.file_handlers.base_mixins import BaseS3URLMixin
from common.aws.s3_utils import get_file_url

class MessageMediaMixin(BaseS3URLMixin):
    """
    Adds, for each media field in signed_fields:
      - "<field>_key"  (S3 object key or None)
      - "<field>_url"  (presigned/public URL or None)

    And also (for non-encrypted messages only):
      - "<field>_download_url" (presigned URL with Content-Disposition=attachment)

    If instance.is_encrypted_file is True (E2EE), all URLs are hidden (set to None).
    """
    # Defaults are None; adjust if you want hard-coded fallbacks for non-existent fields
    signed_fields = {
        "image": None,
        "video": None,
        "audio": None,
        "file":  None,
    }

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get("request")

        # Hide all URLs if this is an end-to-end encrypted file message (DM E2EE)
        if getattr(instance, "is_encrypted_file", False):
            for field in self.signed_fields.keys():
                rep[f"{field}_url"] = None
                rep[f"{field}_download_url"] = None
            return rep

        # Non-encrypted: provide download URLs too (if key exists)
        for field in self.signed_fields.keys():
            key = rep.get(f"{field}_key")
            if key:
                dl_url = get_file_url(key=key, default_url=None, force_download=True)
                if request and dl_url and not (dl_url.startswith("http://") or dl_url.startswith("https://")):
                    dl_url = request.build_absolute_uri(dl_url)
                rep[f"{field}_download_url"] = dl_url
            else:
                rep[f"{field}_download_url"] = None

        return rep
