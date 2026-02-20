# apps/core/square/apps.py

from django.apps import AppConfig


class SquareConfig(AppConfig):
    name = "apps.core.square"

    def ready(self):
        # Load projection registry
        import apps.core.square.projections  # noqa
