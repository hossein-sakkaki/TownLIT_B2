# apps/conversation/apps.py
# TownLIT-Backend
#
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from django.apps import AppConfig


class ConversationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.conversation"

    def ready(self):
        import apps.conversation.signals  # noqa: F401
        import apps.conversation.integrations.organization  # noqa: F401
