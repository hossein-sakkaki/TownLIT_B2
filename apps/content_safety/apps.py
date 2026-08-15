# apps/content_safety/apps.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from django.apps import AppConfig


class ContentSafetyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content_safety"
    verbose_name = "Content Safety"
    