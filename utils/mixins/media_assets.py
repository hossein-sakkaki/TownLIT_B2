# utils/mixins/media_assets.py

from django.db import models


class MediaAssetsMixin(models.Model):
    """
    Stores ready-to-read media metadata and variants.
    """

    media_assets = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        abstract = True

    def set_media_asset(self, field_name: str, payload: dict) -> None:
        assets = dict(self.media_assets or {})
        assets[field_name] = payload or {}
        self.media_assets = assets

    def get_media_asset(self, field_name: str) -> dict:
        assets = self.media_assets or {}
        value = assets.get(field_name)
        return value if isinstance(value, dict) else {}