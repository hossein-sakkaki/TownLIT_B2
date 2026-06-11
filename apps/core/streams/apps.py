# apps/core/streams/apps.py

from django.apps import AppConfig


class StreamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.streams"

    def ready(self):
        # Load stream source registrations.
        import apps.core.streams.sources  # noqa