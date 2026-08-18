# apps/bookstore_inventory/services/orders.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from apps.bookstore_inventory.models import BookOrder


def rebuild_order_totals(order_id):
    order = BookOrder.objects.get(pk=order_id)
    order.recalculate_totals(save=True)
    return order
