# apps/organizations/modules/church/services/slugs.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.utils.text import slugify


def unique_workspace_slug(*, model, workspace, name, exclude_pk=None):
    base = slugify(name)[:150] or "item"
    candidate = base
    suffix = 2

    queryset = model.objects.filter(
        workspace=workspace,
    )

    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    while queryset.filter(slug=candidate).exists():
        tail = f"-{suffix}"
        candidate = f"{base[:180 - len(tail)]}{tail}"
        suffix += 1

    return candidate
