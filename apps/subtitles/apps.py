# apps/subtitles/apps.py

from django.apps import AppConfig


class SubtitlesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.subtitles"
    verbose_name = "Subtitles"

    def ready(self):
        # Register signals
        from .signals import voice_hooks  # noqa