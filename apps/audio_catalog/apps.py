# apps/audio_catalog/apps.py

from django.apps import AppConfig


class AudioCatalogConfig(AppConfig):
    default_auto_field = (
        "django.db.models.BigAutoField"
    )

    name = "apps.audio_catalog"
    verbose_name = "Audio Catalog"

    def ready(self):
        from . import checks  # noqa: F401
        from . import usage_signals  # noqa: F401