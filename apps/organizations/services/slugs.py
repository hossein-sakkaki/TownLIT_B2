# apps/organizations/services/slugs.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-29.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

import uuid

from django.utils.text import slugify

from apps.organizations.models import Organization


MAX_ORGANIZATION_SLUG_LENGTH = 190
RESERVED_ORGANIZATION_SLUGS = {
    "membership-requests",
    "memberships",
    "role-assignments",
    "system",
    "workflow",
}


def generate_unique_organization_slug(name: str) -> str:
    base = slugify(
        " ".join(str(name or "").split()),
        allow_unicode=True,
    )
    base = base[:MAX_ORGANIZATION_SLUG_LENGTH].strip("-")

    if not base:
        base = "organization"

    if (
        base not in RESERVED_ORGANIZATION_SLUGS
        and not Organization.objects.filter(slug=base).exists()
    ):
        return base

    for _ in range(20):
        suffix = uuid.uuid4().hex[:8]
        suffix_room = len(suffix) + 1
        candidate = (
            f"{base[:MAX_ORGANIZATION_SLUG_LENGTH - suffix_room]}"
            f"-{suffix}"
        )

        if (
            candidate not in RESERVED_ORGANIZATION_SLUGS
            and not Organization.objects.filter(slug=candidate).exists()
        ):
            return candidate

    return uuid.uuid4().hex
