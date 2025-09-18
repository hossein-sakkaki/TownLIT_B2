# common/file_handlers/base_mixins.py
# common/file_handlers/base_mixins.py
from common.aws.s3_utils import get_file_url

class BaseS3URLMixin:
    """
    For each entry in `signed_fields = { <field_name>: <default_url> }`, add:
      - "<field_name>_key" -> S3 object key (or None)
      - "<field_name>_url" -> presigned/public URL (absolute if request exists)
    Now supports merging signed_fields across the whole MRO (child overrides win).
    Set SIGNED_FIELDS_MERGE=False in a subclass to keep legacy behavior (self-only).
    """
    signed_fields = {}
    SIGNED_FIELDS_MERGE = True  # 👈 default ON (safe for single-mixin; fixes multi-mixin)

    def _iter_signed_fields(self):
        # Legacy mode: behave exactly like before (no merging)
        if not getattr(self, "SIGNED_FIELDS_MERGE", True):
            yield from (getattr(self, "signed_fields", {}) or {}).items()
            return

        # Merge across MRO: base -> derived; later updates override earlier keys
        merged = {}
        for cls in reversed(self.__class__.mro()):
            # only classes that actually participate in this mixin’s contract
            if hasattr(cls, "signed_fields"):
                data = getattr(cls, "signed_fields") or {}
                if isinstance(data, dict):
                    merged.update(data)  # child wins on duplicates
        yield from merged.items()

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get("request")

        for field, default in self._iter_signed_fields():
            file = getattr(instance, field, None)
            key = getattr(file, "name", None) or None

            # Build URL using your policy (presigned/public/placeholder)
            url = get_file_url(key=key, default_url=default)

            # Make absolute if request exists and url is relative
            if request and url and not (url.startswith("http://") or url.startswith("https://")):
                url = request.build_absolute_uri(url)

            rep[f"{field}_key"] = key
            rep[f"{field}_url"] = url

        return rep
