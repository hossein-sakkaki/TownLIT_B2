# apps/bookstore_inventory/tasks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from celery import shared_task


@shared_task(
    name="apps.bookstore_inventory.tasks.send_daily_inventory_report",
    ignore_result=False,
)
def send_daily_inventory_report():
    """Celery entry point for the manager-facing daily inventory email."""

    from apps.bookstore_inventory.services.daily_reports import (
        send_daily_inventory_summary,
    )

    return send_daily_inventory_summary()
