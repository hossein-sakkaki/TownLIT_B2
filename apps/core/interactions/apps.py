from django.apps import AppConfig


class InteractionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.interactions"

    def ready(self):
        # Import signals on startup
        from . import signals  # noqa
