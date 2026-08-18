# apps/bookstore_inventory/apps.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.apps import AppConfig


class BookstoreInventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bookstore_inventory"
    verbose_name = "Bookstore Inventory"

    def ready(self):
        from . import signals  # noqa: F401
