# apps/advancement/apps.py

from django.apps import AppConfig


class AdvancementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.advancement"
    verbose_name = "Advancement"

    def ready(self):
        # Load dedicated admin registrations
        try:
            import apps.advancement.admin  # noqa
        except Exception:
            pass