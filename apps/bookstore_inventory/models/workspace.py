# apps/bookstore_inventory/models/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from apps.bookstore_inventory.models.warehouse import Warehouse


class BookstoreWorkspace(Warehouse):
    """Menu-only proxy used as the single operational Admin entry point."""

    class Meta:
        proxy = True
        verbose_name = "Bookstore workspace"
        verbose_name_plural = "Bookstore workspace"

