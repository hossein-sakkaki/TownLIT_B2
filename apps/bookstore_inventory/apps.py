# apps/bookstore_inventory/apps.py

from django.apps import AppConfig


class BookstoreInventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bookstore_inventory"
    verbose_name = "Bookstore Inventory"

    def ready(self):
        # Import signals
        from . import signals  # noqa: F401