# apps/organization_content/apps.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-27.
# Last Update by Hossein Sakkaki on 2026-10-20.

from django.apps import AppConfig


class OrganizationContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organization_content"
    verbose_name = "Organization Public Content"


    def ready(self):
        from apps.core.square.registry import (
            SquareContentSource, get_square_source, register_square_source,
        )
        from apps.organization_content.models import OrganizationUpdate

        if get_square_source("organization_update") is None:
            register_square_source(source=SquareContentSource(
                model=OrganizationUpdate,
                kind="organization_update",
                media_fields=[],
                requires_conversion=False,
                search_fields=["caption", "organization__name", "organization__slug"],
            ))
