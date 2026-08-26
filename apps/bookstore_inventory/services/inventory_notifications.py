# apps/bookstore_inventory/services/inventory_notifications.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-24.
# Last Update by Hossein Sakkaki on 2026-08-24.

from __future__ import annotations

from apps.bookstore_inventory.tasks import (
    send_inventory_report,
)


def queue_inventory_change_notification(
    movements,
):
    """
    Queue a full inventory report for a committed stock-changing operation.
    """

    movement_ids = [
        movement.pk
        for movement in movements
        if movement.pk
    ]

    if not movement_ids:
        return

    send_inventory_report.delay(
        movement_ids=movement_ids,
        source="stock_change",
    )