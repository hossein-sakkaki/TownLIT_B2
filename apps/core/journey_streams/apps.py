# apps/core/journey_streams/apps.py

from django.apps import AppConfig


class JourneyStreamsConfig(
    AppConfig,
):
    default_auto_field = (
        "django.db.models.BigAutoField"
    )

    name = (
        "apps.core.journey_streams"
    )

    verbose_name = (
        "Journey Streams"
    )