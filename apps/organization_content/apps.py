# apps/organization_content/apps.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-09-27.

from django.apps import AppConfig


class OrganizationContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organization_content"
    verbose_name = "Organization Public Content"
