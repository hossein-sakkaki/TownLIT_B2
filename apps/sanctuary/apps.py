from django.apps import AppConfig


class SanctuaryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sanctuary'

    def ready(self):
        import apps.sanctuary.signals.signals
