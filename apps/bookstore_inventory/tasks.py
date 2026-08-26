# apps/bookstore_inventory/tasks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-24.

from celery import shared_task


@shared_task(
    name=(
        "apps.bookstore_inventory.tasks."
        "send_inventory_report"
    ),
    ignore_result=False,
)
def send_inventory_report(
    movement_ids=None,
    source="stock_change",
):
    """
    Send the current complete bookstore inventory snapshot.

    Automatic stock changes provide movement IDs.
    Manual sends use the same pipeline without requiring a movement.
    """

    from apps.bookstore_inventory.services.inventory_reports import (
        send_inventory_summary,
    )

    return send_inventory_summary(
        movement_ids=movement_ids,
        source=source,
    )