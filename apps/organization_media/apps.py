# apps/organization_media/apps.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.apps import AppConfig


class OrganizationMediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organization_media"
    verbose_name = "Organization Media"

    def ready(self):
        from .signals import church_teaching_media_cleanup  # noqa: F401
        from .signals import organization_asset_cleanup  # noqa: F401

