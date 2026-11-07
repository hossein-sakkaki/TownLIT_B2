# apps/ai_gateway/apps.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

from django.apps import AppConfig


class AIGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_gateway"
    verbose_name = "AI Gateway metadata"
