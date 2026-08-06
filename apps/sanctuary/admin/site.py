# apps/sanctuary/admin/site.py

from __future__ import annotations

from django.contrib import admin

from .media_preview import (
    sanctuary_admin_media_urls,
)


def install_sanctuary_admin_urls() -> None:
    """
    Install Sanctuary-only admin URLs once.

    Django's standard app admin discovery does not automatically
    append custom views to admin.site.get_urls().
    """

    if getattr(
        admin.site,
        "_townlit_sanctuary_urls_installed",
        False,
    ):
        return

    original_get_urls = (
        admin.site.get_urls
    )

    def get_urls_with_sanctuary():
        return (
            sanctuary_admin_media_urls()
            + original_get_urls()
        )

    admin.site.get_urls = (
        get_urls_with_sanctuary
    )

    admin.site._townlit_sanctuary_urls_installed = (
        True
    )


install_sanctuary_admin_urls()