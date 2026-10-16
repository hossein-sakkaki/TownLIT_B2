# apps/organization_content/feature_flags.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-28.
# Last Update by Hossein Sakkaki on 2026-09-28.

from django.conf import settings
from django.core.exceptions import PermissionDenied


def organization_content_writes_enabled() -> bool:
    return bool(
        getattr(
            settings,
            "ORGANIZATION_CONTENT_WRITES_ENABLED",
            False,
        )
    )


def ensure_organization_content_writes_enabled():
    if not organization_content_writes_enabled():
        raise PermissionDenied(
            "Organization content publishing is not enabled."
        )