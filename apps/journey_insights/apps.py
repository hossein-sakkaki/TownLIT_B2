# apps/journey_insights/apps.py

from django.apps import AppConfig


class JourneyInsightsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.journey_insights"
    verbose_name = "Journey Reflections & Insights"

    def ready(self):
        import apps.journey_insights.signals  # noqa: F401